"""Agent IDs must survive translation of role names (pt-BR roster).

The expected IDs below were captured from the English roster immediately
before the translation. Journals, checkpoints and the capability policy
refer to agents by these IDs, so any change here is a breaking change.
"""
import unittest

from agents import workspace_registry as wr
from agents.cluster_definitions import (
    CLUSTERS, DEVILS_ADVOCATE, MASTER_MANAGER, focused_reviewer_role,
    get_cluster_analysis_prompt, get_cluster_manager_prompt, get_devils_advocate_prompt,
    get_feedback_agent_config, get_feedback_routing_prompt, get_intracluster_vote_prompt,
    get_master_manager_prompt,
)
from security.capability_policy import authorize_agent_action as decide

FROZEN_IDS = [
    "compliance:manager:compliance-cluster-manager",
    "compliance:specialist:anti-corruption-compliance-analyst",
    "compliance:specialist:electronic-signature-validator",
    "compliance:specialist:general-provisions-reviewer",
    "compliance:specialist:lgpd-data-protection-analyst",
    "coordination:adversarial:analista-adversarial-advogado-do-diabo-auditor-de-racioc-nio-jur-dico",
    "coordination:orchestrator:master-manager-final-synthesis-orchestrator",
    "financial_risk:manager:financial-risk-cluster-manager",
    "financial_risk:specialist:economic-exposure-quantifier",
    "financial_risk:specialist:guarantee-security-analyst",
    "financial_risk:specialist:penalty-clause-validator",
    "financial_risk:specialist:price-payment-analyst",
    "foundation:manager:foundation-cluster-manager",
    "foundation:specialist:contract-classifier",
    "foundation:specialist:document-integrity-verifier",
    "foundation:specialist:party-qualification-analyst",
    "foundation:specialist:transactional-context-mapper",
    "mitigation_exit:manager:mitigation-exit-cluster-manager",
    "mitigation_exit:specialist:dispute-resolution-analyst",
    "mitigation_exit:specialist:exit-strategy-evaluator",
    "mitigation_exit:specialist:force-majeure-hardship-analyst",
    "mitigation_exit:specialist:termination-rights-analyst",
    "strategy:manager:strategy-cluster-manager",
    "strategy:specialist:concession-boundary-optimizer",
    "strategy:specialist:counterparty-intent-analyst",
    "strategy:specialist:deal-structure-evaluator",
    "strategy:specialist:negotiation-leverage-assessor"
]


class _Engine:
    def __init__(self, depth, feedback=None):
        self.review_depth, self.feedback_agents = depth, feedback or {}


class AgentIdentityStabilityTests(unittest.TestCase):
    def test_translated_roster_keeps_every_historical_id(self):
        roster = wr.roster_for_engine(_Engine("full"), list(CLUSTERS))
        coordination = wr.coordination_roster()
        ids = [a["id"] for c in roster for a in c["agents"] + [c["manager"]]]
        ids += [coordination["orchestrator"]["id"], coordination["adversarial"]["id"]]
        self.assertEqual(sorted(ids), FROZEN_IDS)

    def test_policy_and_workspace_agree_on_every_agent_id(self):
        for cid, cluster in CLUSTERS.items():
            for kind, definition in [("specialist", a) for a in cluster["agents"]] + [("manager", cluster["manager"])]:
                with self.subTest(agent=definition["key"]):
                    decision = decide(definition, "model_completion", cluster_id=cid, round_num=1)
                    self.assertEqual(decision["outcome"], "ALLOW")
                    self.assertEqual(decision["agent_id"], wr.identity(cid, definition, kind)["id"])
        for kind, definition in (("orchestrator", MASTER_MANAGER), ("adversarial", DEVILS_ADVOCATE)):
            decision = decide(definition, "model_completion", cluster_id="coordination", round_num=1)
            self.assertEqual(decision["agent_id"], wr.identity("coordination", definition, kind)["id"])

    def test_focused_and_feedback_ids_keep_their_historical_form(self):
        roster = wr.roster_for_engine(_Engine("focused"), ["foundation"])
        self.assertEqual(roster[0]["agents"][0]["id"],
                         "foundation:specialist:foundation-document-integrity-reviewer")
        self.assertIn("revisor focado", roster[0]["agents"][0]["display_name"])
        feedback = get_feedback_agent_config("Revisar a cláusula 9", "foundation", 2)
        self.assertEqual(wr.identity("foundation", feedback)["id"],
                         "foundation:specialist:user-feedback-advocate-round-2")
        # A feedback agent restored from a pre-translation checkpoint (English
        # role, no key) keeps the ID it always had.
        legacy = {"role": "User Feedback Advocate (Round 2)", "goal": "g"}
        self.assertEqual(wr.identity("foundation", legacy)["id"],
                         "foundation:specialist:user-feedback-advocate-round-2")

    def test_focused_reviewer_name_has_a_single_source(self):
        cluster = CLUSTERS["compliance"]
        focused = {**cluster["agents"][0], "role": focused_reviewer_role(cluster),
                   "goal": cluster["description"]}
        decision = decide(focused, "model_completion", cluster_id="compliance", round_num=1)
        self.assertEqual(decision["outcome"], "ALLOW")
        self.assertEqual(decision["agent_id"],
                         "compliance:focused:regulatory-compliance-governance-reviewer")

    def test_prompts_keep_machine_readable_field_names(self):
        cluster = CLUSTERS["foundation"]
        agent = cluster["agents"][0]
        summaries = {"foundation": {"raw": "x", "parsed": {"summary": "s"}}}
        prompts = {
            "analysis": (get_cluster_analysis_prompt("DOC", agent, 1, {}),
                         ['"score"', '"confidence_level"', '"key_findings"', '"legal_basis"',
                          '"risk_flags"', "OK|WARNING|VIOLATION|INFO", "Crítico|Relevante|Aceitável"]),
            "vote": (get_intracluster_vote_prompt("a", [], cluster["name"]),
                     ['"scores"', '"confidence_scores"', '"rationale"']),
            "manager": (get_cluster_manager_prompt(cluster, [], {}, 1, {}),
                        ['"aggregated_score"', '"confidence_aggregate"', '"dissent_notes"']),
            "devil": (get_devils_advocate_prompt(summaries, "DOC", 1),
                      ['"gap_severity_score"', '"identified_gaps"', '"unasked_questions"']),
            "master": (get_master_manager_prompt(summaries, None, 1),
                       ['"final_score"', '"final_classification"', '"gate_triggers"']),
            "routing": (get_feedback_routing_prompt("x", summaries),
                        ['"target_cluster"', '"rationale"', '"confidence"']),
        }
        for name, (prompt, fields) in prompts.items():
            with self.subTest(prompt=name):
                for field in fields:
                    self.assertIn(field, prompt)
                self.assertIn("português do Brasil", prompt)


if __name__ == "__main__":
    unittest.main()
