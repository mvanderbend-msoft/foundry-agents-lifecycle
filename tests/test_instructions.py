import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
INSTRUCTIONS_PATH = ROOT / "src" / "support-agent" / "instructions.py"
SPEC = importlib.util.spec_from_file_location("support_agent_instructions", INSTRUCTIONS_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {INSTRUCTIONS_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AGENT_INSTRUCTIONS = MODULE.AGENT_INSTRUCTIONS
DEV_SERVICENOW_MOCK_INSTRUCTIONS = MODULE.DEV_SERVICENOW_MOCK_INSTRUCTIONS


class AgentInstructionsTests(unittest.TestCase):
    def test_does_not_fabricate_servicenow_evidence(self):
        self.assertIn("Do not fabricate ServiceNow evidence", AGENT_INSTRUCTIONS)

    def test_priority_changes_require_explicit_authorization(self):
        self.assertIn("explicitly authorized write request", AGENT_INSTRUCTIONS)
        self.assertIn(
            "state exactly what is needed before the change can proceed",
            AGENT_INSTRUCTIONS,
        )

    def test_agent_remains_isolated(self):
        self.assertIn("Do not call SupervisorAgent", AGENT_INSTRUCTIONS)
        self.assertIn("offer a concise handoff message", AGENT_INSTRUCTIONS)

    def test_incident_assessment_requires_json(self):
        self.assertIn("Return ONLY JSON", AGENT_INSTRUCTIONS)

    def test_dev_mock_is_explicit_and_non_fabricating(self):
        self.assertIn("DEV_SERVICENOW_MOCK_OK", DEV_SERVICENOW_MOCK_INSTRUCTIONS)
        self.assertIn("Never claim that an incident", DEV_SERVICENOW_MOCK_INSTRUCTIONS)
        self.assertIn(
            "Do not mention the DEV environment",
            DEV_SERVICENOW_MOCK_INSTRUCTIONS,
        )
        self.assertIn(
            "unless\n"
            "the user explicitly asks you to confirm the configured mock mode",
            DEV_SERVICENOW_MOCK_INSTRUCTIONS,
        )


if __name__ == "__main__":
    unittest.main()
