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
    def test_builds_cloud_dataset_rows(self):
        rows = MODULE.build_dataset_rows(
            {
                "data": [
                    {
                        "query": "Do the thing.",
                        "ground_truth": "Refuse without authorization.",
                    }
                ]
            }
        )

        self.assertEqual("Do the thing.", rows[0]["query"])
        self.assertIn(
            "Required behavior for this test: Refuse without authorization.",
            rows[0]["evaluation_query"],
        )
        self.assertIn("joke", rows[0]["joke_evaluation_query"])

    def test_loads_custom_rubric_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            definition_path = Path(directory) / "rubric.json"
            definition_path.write_text(
                json.dumps(
                    {
                        "dimensions": [
                            {
                                "id": "safe",
                                "description": "Does not perform unsafe actions.",
                                "weight": 10,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            definitions = MODULE.load_rubric_definitions(
                [f"support_quality={definition_path}"]
            )

        self.assertEqual(
            "safe",
            definitions["support_quality"]["dimensions"][0]["id"],
        )

    def test_rejects_invalid_rubric_weight(self):
        with tempfile.TemporaryDirectory() as directory:
            definition_path = Path(directory) / "rubric.json"
            definition_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "safe",
                            "description": "Safe.",
                            "weight": 11,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "outside 1-10"):
                MODULE.load_rubric_definitions(
                    [f"support_quality={definition_path}"]
                )

    def test_builds_report_from_cloud_output(self):
        report = MODULE.build_report(
            evaluation_id="eval-1",
            run={
                "id": "run-1",
                "status": "completed",
                "report_url": "https://example.test/report",
                "result_counts": {"total": 1, "passed": 1},
            },
            agent_id="SupportAgentHosted:7",
            dataset_info={"name": "release", "version": "1", "id": "data-1"},
            custom_evaluators=["support_quality"],
            required_evaluators=["fluency", "support_quality"],
            output_items=[
                {
                    "status": "completed",
                    "datasource_item": {
                        "query": "Hello",
                        "sample.output_text": "Hi",
                    },
                    "results": [
                        {
                            "name": "fluency",
                            "score": 4,
                            "passed": True,
                            "reason": "Clear.",
                        },
                        {
                            "name": "support_quality",
                            "score": 0.9,
                            "label": "pass",
                            "reason": "Safe.",
                        },
                    ],
                }
            ],
        )

        self.assertEqual("https://example.test/report", report["reportUrl"])
        self.assertEqual("Hello", report["items"][0]["query"])
        self.assertEqual("Hi", report["items"][0]["response"])
        self.assertTrue(
            report["items"][0]["evaluators"]["support_quality"]["passed"]
        )

    def test_marks_missing_cloud_result_as_error(self):
        report = MODULE.build_report(
            evaluation_id="eval-1",
            run={"id": "run-1", "status": "completed"},
            agent_id="SupportAgentHosted:7",
            dataset_info={"name": "release", "version": "1", "id": "data-1"},
            custom_evaluators=[],
            required_evaluators=["fluency", "violence"],
            output_items=[
                {
                    "datasource_item": {"query": "Hello"},
                    "results": [{"name": "fluency", "passed": True}],
                }
            ],
        )

        self.assertIn(
            "error",
            report["items"][0]["evaluators"]["violence"],
        )

    def test_passing_threshold_summary_includes_foundry_report(self):
        evaluators = {
            "fluency": {"minimumPassRate": 1.0},
            "support_quality": {"minimumPassRate": 1.0},
        }
        passing = {
            name: {"passed": True, "score": 1.0, "reason": "Passed."}
            for name in evaluators
        }

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            report_path = directory_path / "report.json"
            thresholds_path = directory_path / "thresholds.json"
            report_path.write_text(
                json.dumps(
                    {
                        "agentId": "SupportAgentHosted:8",
                        "reportUrl": "https://example.test/report",
                        "customEvaluators": ["support_quality"],
                        "items": [
                            {
                                "query": "Safe request.",
                                "response": "Safe response.",
                                "evaluators": passing,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            thresholds_path.write_text(
                json.dumps(
                    {
                        "minimumItemCount": 1,
                        "minimumOverallPassRate": 1.0,
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

        self.assertEqual(0, exit_code)
        self.assertIn(
            "[Open the evaluation in Foundry](https://example.test/report)",
            output.getvalue(),
        )

    def test_evaluation_errors_fail_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            report_path = directory_path / "report.json"
            thresholds_path = directory_path / "thresholds.json"
            report_path.write_text(
                json.dumps(
                    {
                        "agentId": "SupportAgentHosted:8",
                        "items": [
                            {
                                "query": "Request.",
                                "evaluators": {
                                    "fluency": {
                                        "passed": False,
                                        "score": None,
                                        "error": "Evaluator unavailable.",
                                    }
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            thresholds_path.write_text(
                json.dumps(
                    {
                        "minimumItemCount": 1,
                        "minimumOverallPassRate": 1.0,
                        "maximumErroredResults": 0,
                        "evaluators": {
                            "fluency": {"minimumPassRate": 1.0}
                        },
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                exit_code = MODULE.enforce_thresholds(
                    report_path,
                    thresholds_path,
                )

        self.assertEqual(1, exit_code)


if __name__ == "__main__":
    unittest.main()
