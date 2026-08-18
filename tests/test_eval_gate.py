import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_eval_gate.py"
SPEC = importlib.util.spec_from_file_location("run_eval_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvaluationGateTests(unittest.TestCase):
    def test_extracts_completed_raw_response(self):
        output = (
            "event: response.output_text.done\n"
            '\ufeff  data: {"type":"response.output_text.done",'
            '"text":"Evaluation response"}\n'
        )

        self.assertEqual(
            ("Evaluation response", []),
            MODULE.extract_response(output),
        )

    def test_falls_back_to_raw_response_deltas(self):
        output = (
            'data: {"type":"response.output_text.delta","delta":"Evaluation "}\n'
            'data: {"type":"response.output_text.delta","delta":"response"}\n'
        )

        self.assertEqual(
            ("Evaluation response", []),
            MODULE.extract_response(output),
        )

    def test_rejects_empty_response(self):
        with self.assertRaisesRegex(RuntimeError, "captured 26 characters"):
            MODULE.extract_response("event: response.completed\n")

    def test_reports_failed_response_details(self):
        output = (
            "event: response.failed\n"
            'data: {"type":"response.failed","response":{"error":'
            '{"code":"server_error","message":"Backend unavailable"}}}\n'
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "server_error: Backend unavailable",
        ):
            MODULE.extract_response(output)

    def test_extracts_tool_call_evidence(self):
        output = (
            'data: {"type":"response.output_item.done","item":'
            '{"id":"call-1","type":"mcp_call","name":"List Records"}}\n'
            'data: {"type":"response.output_text.done","text":"Done"}\n'
        )

        response, tool_calls = MODULE.extract_response(output)

        self.assertEqual("Done", response)
        self.assertEqual("List Records", tool_calls[0]["name"])

    def test_derives_resource_endpoint(self):
        endpoint = (
            "https://example.services.ai.azure.com/api/projects/example-project"
        )

        self.assertEqual(
            "https://example.services.ai.azure.com",
            MODULE.project_resource_endpoint(endpoint),
        )

    def test_accepts_violence_score_without_result_field(self):
        self.assertTrue(
            MODULE.evaluator_passed(
                "violence",
                {"violence": "Very low", "violence_score": 0.0},
            )
        )

    def test_detects_incomplete_violence_result(self):
        self.assertFalse(
            MODULE.evaluator_has_result(
                "violence",
                {"violence": None, "violence_score": None},
            )
        )

    def test_evaluation_summary_distinguishes_invocation_errors(self):
        evaluators = {
            "fluency": {"minimumPassRate": 0.8},
            "task_adherence": {"minimumPassRate": 0.8},
            "violence": {"minimumPassRate": 1.0},
        }
        passing = {
            name: {"passed": True, "score": 1.0, "reason": "Passed."}
            for name in evaluators
        }
        invocation_error = "RuntimeError: server_error: Backend unavailable"
        errored = {
            name: {"passed": False, "score": None, "error": invocation_error}
            for name in evaluators
        }

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            report_path = directory_path / "report.json"
            thresholds_path = directory_path / "thresholds.json"
            report_path.write_text(
                json.dumps(
                    {
                        "agentId": "SupportAgentHosted:7",
                        "items": [
                            {"query": "Passing case one", "evaluators": passing},
                            {"query": "Passing case two", "evaluators": passing},
                            {"query": "Failing invocation", "evaluators": errored},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            thresholds_path.write_text(
                json.dumps(
                    {
                        "minimumItemCount": 3,
                        "minimumOverallPassRate": 0.8,
                        "maximumErroredResults": 0,
                        "evaluators": evaluators,
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = MODULE.enforce_thresholds(
                    report_path,
                    thresholds_path,
                )

        summary = output.getvalue()
        self.assertEqual(1, exit_code)
        self.assertIn("| `fluency` | 100.0% | 2/2 | 1 |", summary)
        self.assertIn("## Failed cases", summary)
        self.assertIn("Failing invocation", summary)
        self.assertIn(invocation_error, summary)


if __name__ == "__main__":
    unittest.main()
