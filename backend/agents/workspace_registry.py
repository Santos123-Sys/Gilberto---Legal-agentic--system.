"""Presentation identities derived from the engine roster, never new legal agents.

Roles are retained verbatim to join existing journal records. IDs are stable
across ordering changes; feedback identities include their recorded round.
No prompt, weighting, or professional qualification is changed by this registry.
"""
import hashlib
import re

from agents.cluster_definitions import CLUSTERS, DEVILS_ADVOCATE, MASTER_MANAGER


STYLES = {
    "foundation": "Systematic and precise; checks document completeness and context.",
    "financial_risk": "Quantitative and methodical; separates amounts from legal conclusions.",
    "mitigation_exit": "Scenario-oriented; examines obligations and available exit routes.",
    "compliance": "Meticulous and skeptical; flags unsupported compliance claims.",
    "strategy": "Critical and pragmatic; identifies trade-offs and competing positions.",
}


def identity(cluster_id, definition, kind="specialist"):
    role = definition["role"]
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    stable_id = f"{cluster_id}:{kind}:{slug}"
    return {
        "id": stable_id, "role": role, "display_name": role,
        "cluster_id": cluster_id, "kind": kind,
        "avatar_key": hashlib.sha256(stable_id.encode()).hexdigest()[:12],
        "specialization": definition.get("goal", ""),
        "working_style": STYLES.get(cluster_id, "Integrative and evidence-focused.")
            if kind != "adversarial" else "Adversarial and critical; challenges assumptions and evidence gaps.",
        "identity_notice": "AI role; does not represent a licensed lawyer.",
    }


def roster_for_engine(engine, active_ids):
    roster = []
    for cid in active_ids:
        cluster = CLUSTERS[cid]
        definitions = cluster["agents"]
        if engine.review_depth == "focused":
            definitions = [{"role": cluster["name"] + " reviewer", "goal": cluster["description"]}]
        definitions = definitions + engine.feedback_agents.get(cid, [])
        roster.append({
            "id": cid, "name": cluster["name"], "color": cluster["color"],
            "manager": identity(cid, cluster["manager"], "manager"),
            "agents": [identity(cid, definition) for definition in definitions],
            "execution_order": "specialists_sequential_then_peer_votes_then_manager",
        })
    return roster


def coordination_roster():
    return {
        "orchestrator": identity("coordination", MASTER_MANAGER, "orchestrator"),
        "adversarial": identity("coordination", DEVILS_ADVOCATE, "adversarial"),
        "dependencies": ["active_clusters", "adversarial_review", "master_synthesis", "human_review"],
    }
