import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_eval_gate.py"
SPEC = importlib.util.spec_from_file_location("run_eval_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvaluationGateTests(unittest.TestCase):
    def test_cleans_rendered_agent_output(self):
        output = (
            "Agent: SupportAgentHosted\n"
            "Endpoint: https://example.test\n"
            "Version: 5\n"
            "Protocol: responses\n"
            "Message: Test\n"
            "Connected to remote agent\n"
            "Session: abc\n"
            "Conversation: ghi\n"
            "Invocation: def\n"
            "\x1b[32mEvaluation response\x1b[0m\n"
        )

        self.assertEqual("Evaluation response", MODULE.clean_agent_output(output))

    def test_rejects_empty_response(self):
        with self.assertRaisesRegex(RuntimeError, "without a textual response"):
            MODULE.clean_agent_output("Session: abc\nInvocation: def\n")

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
