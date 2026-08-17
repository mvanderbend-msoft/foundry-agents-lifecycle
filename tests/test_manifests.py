import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.azure = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
        cls.agent = yaml.safe_load(
            (ROOT / "src" / "support-agent" / "agent.yaml").read_text(
                encoding="utf-8"
            )
        )
        cls.dev = json.loads(
            (ROOT / "config" / "dev.json").read_text(encoding="utf-8")
        )
        cls.prod = json.loads(
            (ROOT / "config" / "prod.json").read_text(encoding="utf-8")
        )
        cls.thresholds = json.loads(
            (ROOT / "evals" / "thresholds.json").read_text(encoding="utf-8")
        )
        cls.dev_toolbox = yaml.safe_load(
            (ROOT / cls.dev["toolboxDefinition"]).read_text(encoding="utf-8")
        )
        cls.prod_toolbox = yaml.safe_load(
            (ROOT / cls.prod["toolboxDefinition"]).read_text(encoding="utf-8")
        )
        cls.main_source = (
            ROOT / "src" / "support-agent" / "main.py"
        ).read_text(encoding="utf-8")

    def test_agent_identity_matches(self):
        service = self.azure["services"]["support-agent"]
        self.assertEqual(service["name"], self.agent["name"])
        self.assertEqual("hosted", service["kind"])
        self.assertEqual("hosted", self.agent["kind"])

    def test_protocol_matches(self):
        service_protocol = self.azure["services"]["support-agent"]["protocols"][0]
        self.assertEqual(service_protocol, self.agent["protocols"][0])

    def test_toolboxes_use_environment_connections(self):
        self.assertEqual(
            self.dev["serviceNowConnection"],
            self.dev_toolbox["connections"][0]["name"],
        )
        self.assertEqual(
            self.prod["serviceNowConnection"],
            self.prod_toolbox["connections"][0]["name"],
        )

    def test_toolboxes_include_web_search(self):
        for toolbox in (self.dev_toolbox, self.prod_toolbox):
            self.assertIn(
                {"type": "web_search", "name": "web_search"},
                toolbox["tools"],
            )

    def test_toolbox_agent_keeps_response_state(self):
        self.assertNotIn('"store": False', self.main_source)

    def test_only_dev_and_prod_are_configured(self):
        self.assertEqual("dev", self.dev["environment"])
        self.assertEqual("prod", self.prod["environment"])

    def test_environment_projects_are_isolated(self):
        self.assertNotEqual(self.dev["projectEndpoint"], self.prod["projectEndpoint"])

    def test_runtime_dependencies_match_across_environments(self):
        self.assertEqual(self.dev["modelDeployment"], self.prod["modelDeployment"])
        self.assertEqual(self.dev["toolboxName"], self.prod["toolboxName"])

    def test_evaluation_thresholds_are_release_gates(self):
        self.assertGreaterEqual(self.thresholds["minimumItemCount"], 1)
        self.assertGreaterEqual(self.thresholds["minimumOverallPassRate"], 0.8)
        self.assertEqual(0, self.thresholds["maximumErroredResults"])
        self.assertEqual(
            {"fluency", "task_adherence", "violence"},
            set(self.thresholds["evaluators"]),
        )
        for evaluator in self.thresholds["evaluators"].values():
            self.assertGreaterEqual(evaluator["minimumPassRate"], 0)
            self.assertLessEqual(evaluator["minimumPassRate"], 1)


if __name__ == "__main__":
    unittest.main()
