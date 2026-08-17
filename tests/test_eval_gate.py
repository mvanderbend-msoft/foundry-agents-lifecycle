import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_eval_gate.py"
SPEC = importlib.util.spec_from_file_location("run_eval_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvaluationGateTests(unittest.TestCase):
    def test_extracts_text_from_completed_response(self):
        raw = (
            "event: response.completed\n"
            'data: {"response":{"output":[{"type":"message","content":'
            '[{"type":"output_text","text":"Evaluation response"}]}]}}'
        )

        self.assertEqual("Evaluation response", MODULE.extract_response_text(raw))

    def test_falls_back_to_streamed_text(self):
        raw = (
            "event: response.output_text.delta\n"
            'data: {"delta":"Evaluation "}\n'
            "event: response.output_text.delta\n"
            'data: {"delta":"response"}\n'
            "event: response.completed\n"
            'data: {"response":{"output":[]}}'
        )

        self.assertEqual("Evaluation response", MODULE.extract_response_text(raw))

    def test_uses_event_type_from_data_payload(self):
        raw = (
            'data: {"type":"response.output_text.delta","delta":"Evaluation "}\n'
            'data: {"type":"response.output_text.delta","delta":"response"}'
        )

        self.assertEqual("Evaluation response", MODULE.extract_response_text(raw))

    def test_rejects_empty_response(self):
        with self.assertRaisesRegex(RuntimeError, "without a textual response"):
            MODULE.extract_response_text(
                'event: response.completed\ndata: {"response":{"output":[]}}'
            )

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
