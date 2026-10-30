import unittest
from types import SimpleNamespace

from agents.cluster_definitions import CLUSTERS
from agents.workspace_registry import roster_for_engine, coordination_roster


class WorkspaceRegistryTests(unittest.TestCase):
    def test_full_roster_is_exact_engine_roster_with_unique_stable_ids(self):
        engine = SimpleNamespace(review_depth="full", feedback_agents={})
        roster = roster_for_engine(engine, list(CLUSTERS))
        self.assertEqual(len(roster), 5)
        agents = [a for c in roster for a in c["agents"]]
        self.assertEqual(len(agents), 20)
        self.assertEqual(len({a["id"] for a in agents}), 20)
        self.assertEqual(len({a["avatar_key"] for a in agents}), 20)
        for c in roster:
            self.assertEqual([a["role"] for a in c["agents"]], [a["role"] for a in CLUSTERS[c["id"]]["agents"]])
        self.assertEqual(roster_for_engine(engine, ["foundation"])[0], roster[0])

    def test_scoped_focused_and_feedback_rosters_match_execution(self):
        engine = SimpleNamespace(review_depth="focused", feedback_agents={"foundation": [{
            "role": "User Feedback Advocate (Round 2)", "goal": "Review feedback"}]})
        roster = roster_for_engine(engine, ["foundation"])
        self.assertEqual(len(roster), 1)
        self.assertEqual([a["role"] for a in roster[0]["agents"]], [
            "Fundamentos e Integridade Documental — revisor focado", "User Feedback Advocate (Round 2)"])
        self.assertEqual(coordination_roster()["adversarial"]["kind"], "adversarial")
