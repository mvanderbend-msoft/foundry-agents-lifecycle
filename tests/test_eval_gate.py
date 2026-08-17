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

        self.assertEqual("Evaluation response", MODULE.extract_response_text(output))

    def test_falls_back_to_raw_response_deltas(self):
        output = (
            'data: {"type":"response.output_text.delta","delta":"Evaluation "}\n'
            'data: {"type":"response.output_text.delta","delta":"response"}\n'
        )

        self.assertEqual("Evaluation response", MODULE.extract_response_text(output))

    def test_rejects_empty_response(self):
        with self.assertRaisesRegex(RuntimeError, "without a textual response"):
            MODULE.extract_response_text("event: response.completed\n")

    def test_derives_resource_endpoint(self):
        endpoint = (
            "https://example.services.ai.azure.com/api/projects/example-project"
        )

        self.assertEqual(
            "https://example.services.ai.azure.com",
            MODULE.project_resource_endpoint(endpoint),
        )


if __name__ == "__main__":
    unittest.main()
