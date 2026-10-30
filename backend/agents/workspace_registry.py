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


ROLE_STYLES = {
    "Contract Classifier": "Classifies transaction type and checks contractual structure.",
    "Document Integrity Verifier": "Examines document consistency and missing records.",
    "Party Qualification Analyst": "Checks parties, authority and identity information.",
    "Transactional Context Mapper": "Maps commercial context and connected obligations.",
    "Price & Payment Analyst": "Reconciles payment mechanics with documentary evidence.",
    "Penalty Clause Validator": "Tests penalty structure against applicable Brazilian sources.",
    "Guarantee & Security Analyst": "Examines security provisions and enforceability assumptions.",
    "Economic Exposure Quantifier": "Quantifies downside scenarios separately from legal conclusions.",
    "Termination Rights Analyst": "Examines notice, termination triggers and consequences.",
    "Force Majeure & Hardship Analyst": "Tests exceptional-event assumptions and allocation of risk.",
    "Dispute Resolution Analyst": "Examines jurisdiction and dispute-resolution clauses.",
    "Exit Strategy Evaluator": "Maps exit options, conditions and residual obligations.",
    "LGPD & Data Protection Analyst": "Checks Brazilian personal-data protection obligations.",
    "Anti-Corruption Compliance Analyst": "Tests integrity controls and anti-corruption provisions.",
    "Electronic Signature Validator": "Examines signature mechanics and legal validity caveats.",
    "General Provisions Reviewer": "Audits consistency of general contractual clauses.",
    "Negotiation Leverage Assessor": "Evaluates negotiation leverage and documented constraints.",
    "Concession Boundary Optimizer": "Assesses trade-offs and non-negotiable boundaries.",
    "Counterparty Intent Analyst": "Challenges assumptions about counterparty intent.",
    "Deal Structure Evaluator": "Compares alternative contractual and transactional structures.",
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
        "working_style": (ROLE_STYLES.get(role, STYLES.get(cluster_id, "Integrative and evidence-focused."))
                          if kind not in ("adversarial", "orchestrator") else
                          ("Adversarial and critical; challenges unsupported conclusions." if kind == "adversarial"
                           else "Integrates validated cluster results and routes mandatory reviews.")),
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
