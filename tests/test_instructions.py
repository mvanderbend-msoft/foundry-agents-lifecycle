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


class AgentInstructionsTests(unittest.TestCase):
    def test_does_not_fabricate_servicenow_evidence(self):
        self.assertIn("Do not fabricate ServiceNow evidence", AGENT_INSTRUCTIONS)

    def test_priority_changes_require_explicit_authorization(self):
        self.assertIn("explicitly authorized write request", AGENT_INSTRUCTIONS)

    def test_agent_remains_isolated(self):
        self.assertIn("Do not call SupervisorAgent", AGENT_INSTRUCTIONS)

    def test_incident_assessment_requires_json(self):
        self.assertIn("Return ONLY JSON", AGENT_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
