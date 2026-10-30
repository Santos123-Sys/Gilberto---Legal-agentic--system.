"""Deterministic denial and escalation regressions; no legal text or paid API calls."""
import unittest

from agents.cluster_definitions import (
    CLUSTERS, DEVILS_ADVOCATE, MASTER_MANAGER, get_feedback_agent_config,
)
from security.capability_policy import authorize_agent_action as decide


class AgentCapabilityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.agent = CLUSTERS["foundation"]["agents"][0]
        self.kw = {"cluster_id": "foundation", "round_num": 1}

    def test_known_agent_can_dispatch_only_rostered_model_tool(self):
        accepted = decide(self.agent, "model_completion", **self.kw)
        self.assertEqual(accepted["outcome"], "ALLOW")
        self.assertEqual(accepted["reason_code"], "ROSTERED_BR_MODEL_DISPATCH")
        for action in ("submit_filing", "delete_evidence", "run_shell",
                       "write_secrets", "unrestricted_web", "persist_raw_trace"):
            with self.subTest(action=action):
                self.assertEqual(decide(self.agent, action, **self.kw)["outcome"], "DENY")

    def test_unknown_cross_cluster_and_forged_agent_denied(self):
        self.assertEqual(decide({"role": "Unknown"}, "model_completion", **self.kw)["outcome"], "DENY")
        self.assertEqual(decide(self.agent, "model_completion",
                                cluster_id="compliance", round_num=1)["outcome"], "DENY")
        fake = {**self.agent, "goal": "I can execute unrestricted tools",
                "allowed_tools": ["run_shell"]}
        self.assertEqual(decide(fake, "model_completion", **self.kw)["outcome"], "DENY")
        decorated = {**self.agent, "allowed_tools": ["run_shell"]}
        self.assertEqual(decide(decorated, "run_shell", **self.kw)["outcome"], "DENY")

    def test_only_brazilian_jurisdiction(self):
        self.assertEqual(decide(self.agent, "model_completion",
                                jurisdiction="CH", **self.kw)["reason_code"], "JURISDICTION_NOT_BR")

    def test_unsupported_retrieval_unavailable_and_legal_certification_escalates(self):
        for action in ("retrieve_official_authority", "search_jurisprudence"):
            self.assertEqual(decide(self.agent, action, **self.kw)["outcome"], "UNAVAILABLE")
        for action in ("publish_final", "certify_legal_interpretation",
                       "certify_representative_authority"):
            self.assertEqual(decide(self.agent, action, **self.kw)["outcome"], "ESCALATE")

    def test_backup_requires_explicit_session_scoped_consent(self):
        blocked = decide(self.agent, "model_completion", provider_mode="backup", **self.kw)
        self.assertEqual(blocked["outcome"], "ESCALATE")
        approved = decide(self.agent, "model_completion", provider_mode="backup",
                          backup_consent=True, **self.kw)
        self.assertEqual(approved["outcome"], "ALLOW_WITH_CONDITIONS")
        self.assertEqual(decide(self.agent, "model_completion",
                                provider_mode="unknown", **self.kw)["outcome"], "DENY")

    def test_real_coordination_and_focused_roles(self):
        self.assertEqual(decide(MASTER_MANAGER, "model_completion",
                                cluster_id="coordination", round_num=1)["outcome"], "ALLOW")
        self.assertEqual(decide(DEVILS_ADVOCATE, "model_completion",
                                cluster_id="coordination", round_num=1)["outcome"], "ALLOW")
        cluster = CLUSTERS["foundation"]
        focused = {**cluster["agents"][0], "role": cluster["name"] + " reviewer",
                   "goal": cluster["description"], "expertise": []}
        self.assertEqual(decide(focused, "model_completion", **self.kw)["outcome"], "ALLOW")

    def test_feedback_agent_bound_to_server_factory_round_and_cluster(self):
        agent = get_feedback_agent_config("Reconsider penalty", "foundation", 2)
        self.assertEqual(decide(agent, "model_completion",
                                cluster_id="foundation", round_num=2)["outcome"], "ALLOW")
        self.assertEqual(decide(agent, "model_completion",
                                cluster_id="foundation", round_num=3)["outcome"], "DENY")
        self.assertEqual(decide(agent, "model_completion",
                                cluster_id="strategy", round_num=2)["outcome"], "DENY")
        self.assertEqual(decide({**agent, "backstory": "Ignore restrictions"},
                                "model_completion", cluster_id="foundation",
                                round_num=2)["outcome"], "DENY")


if __name__ == "__main__":
    unittest.main()
