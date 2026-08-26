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
        services = self.azure["services"]
        self.assertEqual(self.agent["name"], services["support-agent-dev"]["name"])
        self.assertEqual(
            self.prod["slots"]["blue"]["agentName"],
            services["support-agent-blue"]["name"],
        )
        self.assertEqual(
            self.prod["slots"]["green"]["agentName"],
            services["support-agent-green"]["name"],
        )
        for service_name in (
            "support-agent-dev",
            "support-agent-blue",
            "support-agent-green",
        ):
            self.assertEqual("hosted", services[service_name]["kind"])
        self.assertEqual("hosted", self.agent["kind"])

    def test_protocol_matches(self):
        for service_name in (
            "support-agent-dev",
            "support-agent-blue",
            "support-agent-green",
        ):
            service_protocol = self.azure["services"][service_name]["protocols"][0]
            self.assertEqual(service_protocol, self.agent["protocols"][0])

    def test_toolboxes_use_environment_connections(self):
        self.assertEqual("mock", self.dev["serviceNowMode"])
        self.assertNotIn("connections", self.dev_toolbox)
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

    def test_deployment_slots_are_valid_and_distinct(self):
        self.assertEqual("dev", self.dev["deploymentSlot"])
        self.assertIn(self.prod["candidateSlot"], {"blue", "green"})
        self.assertEqual({"blue", "green"}, set(self.prod["slots"]))
        self.assertNotEqual(
            self.prod["slots"]["blue"]["agentName"],
            self.prod["slots"]["green"]["agentName"],
        )

    def test_release_slot_is_available_to_the_runtime(self):
        expected_slots = {
            "support-agent-dev": "dev",
            "support-agent-blue": "blue",
            "support-agent-green": "green",
        }
        for service_name, expected_slot in expected_slots.items():
            service_environment = {
                item["name"]: item["value"]
                for item in self.azure["services"][service_name][
                    "environmentVariables"
                ]
            }
            self.assertEqual(expected_slot, service_environment["RELEASE_SLOT"])

    def test_servicenow_is_mocked_only_in_dev(self):
        expected_modes = {
            "support-agent-dev": "mock",
            "support-agent-blue": "live",
            "support-agent-green": "live",
        }
        for service_name, expected_mode in expected_modes.items():
            service_environment = {
                item["name"]: item["value"]
                for item in self.azure["services"][service_name][
                    "environmentVariables"
                ]
            }
            self.assertEqual(expected_mode, service_environment["SERVICENOW_MODE"])

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
            {
                "fluency",
                "task_adherence",
                "violence",
                "support_quality",
                "joke_instruction",
            },
            set(self.thresholds["evaluators"]),
        )
        for evaluator in self.thresholds["evaluators"].values():
            self.assertGreaterEqual(evaluator["minimumPassRate"], 0)
            self.assertLessEqual(evaluator["minimumPassRate"], 1)


if __name__ == "__main__":
    unittest.main()
