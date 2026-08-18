import importlib.util
import unittest
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


if __name__ == "__main__":
    unittest.main()
