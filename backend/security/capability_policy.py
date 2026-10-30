"""Fail-closed, server-side capability contracts for the Brazilian-law swarm.

No LLM output, frontend permission, or agent-provided tool list can authorize a
new action. These contracts currently cover the existing model-dispatch path.
Future retrieval/tool adapters MUST enforce this policy at their own boundary.
"""
from collections.abc import Mapping

from agents.cluster_definitions import (
    CLUSTERS, DEVILS_ADVOCATE, MASTER_MANAGER, get_feedback_agent_config,
)

POLICY_VERSION = "br-agent-tools-v1"
DECISIONS = frozenset({"ALLOW", "ALLOW_WITH_CONDITIONS", "ESCALATE", "DENY", "UNAVAILABLE"})
TOOL_MODEL_COMPLETION = "model_completion"


def _decision(outcome, code, agent_id=None, **extra):
    return {
        "outcome": outcome, "reason_code": code, "agent_id": agent_id,
        "policy_version": POLICY_VERSION, **extra,
    }


def _agent_identity(agent, cluster_id, round_num):
    """Resolve actual server-defined agents; never trust a supplied 'allowed_tools'."""
    if not isinstance(agent, Mapping) or not isinstance(cluster_id, str):
        return None
    role = agent.get("role")
    if not isinstance(role, str) or not role:
        return None
    if cluster_id == "coordination":
        for kind, definition in (("orchestrator", MASTER_MANAGER),
                                 ("adversarial", DEVILS_ADVOCATE)):
            if role == definition.get("role") and all(
                    agent.get(field) == definition.get(field)
                    for field in ("role", "goal", "backstory")):
                return f"coordination:{kind}:{role}"
        return None
    cluster = CLUSTERS.get(cluster_id)
    if not cluster:
        return None
    candidates = [("specialist", a) for a in cluster["agents"]]
    candidates.append(("manager", cluster["manager"]))
    for kind, definition in candidates:
        if all(agent.get(field) == definition.get(field)
               for field in ("role", "goal", "backstory")):
            return f"{cluster_id}:{kind}:{role}"
    # Focused mode is a collapsed, known workstream, not a new free-form role.
    if (role == cluster["name"] + " reviewer"
            and agent.get("goal") == cluster["description"]
            and agent.get("backstory") == cluster["agents"][0]["backstory"]
            and agent.get("is_feedback_agent") is not True):
        return f"{cluster_id}:focused:{role}"
    # A feedback advocate's configuration must match the deterministic server
    # factory, its assigned cluster, and the currently executing round.
    if agent.get("is_feedback_agent") is True and type(round_num) is int and round_num >= 1:
        feedback = agent.get("feedback_text")
        if isinstance(feedback, str) and agent.get("target_cluster") == cluster_id:
            expected = get_feedback_agent_config(feedback, cluster_id, round_num)
            if all(agent.get(field) == expected.get(field)
                   for field in ("role", "goal", "backstory", "is_feedback_agent",
                                 "feedback_text", "target_cluster", "round")):
                return f"{cluster_id}:feedback:{round_num}"
    return None


def authorize_agent_action(agent, action, *, cluster_id, round_num,
                           jurisdiction="BR", provider_mode="primary",
                           backup_consent=False):
    """Return a structured decision. No caller-specified permissions are accepted.

    For a model request, ALLOW or ALLOW_WITH_CONDITIONS means the preconditions
    have already been checked here; every other status blocks execution.
    """
    if jurisdiction != "BR":
        return _decision("DENY", "JURISDICTION_NOT_BR")
    agent_id = _agent_identity(agent, cluster_id, round_num)
    if agent_id is None:
        return _decision("DENY", "UNKNOWN_OR_CROSS_CLUSTER_AGENT")
    if action in ("publish_final", "certify_legal_interpretation",
                  "certify_representative_authority"):
        return _decision("ESCALATE", "QUALIFIED_LAWYER_REVIEW_REQUIRED", agent_id)
    if action in ("retrieve_official_authority", "search_jurisprudence"):
        return _decision("UNAVAILABLE", "NO_AUTHORIZED_RETRIEVAL_ADAPTER", agent_id)
    if action != TOOL_MODEL_COMPLETION:
        return _decision("DENY", "TOOL_NOT_ALLOWLISTED", agent_id)
    if provider_mode not in ("primary", "backup"):
        return _decision("DENY", "UNRECOGNIZED_PROVIDER_ROUTE", agent_id)
    if provider_mode == "backup":
        if backup_consent is not True:
            return _decision("ESCALATE", "EXPLICIT_BACKUP_TRANSFER_CONSENT_REQUIRED",
                             agent_id)
        return _decision("ALLOW_WITH_CONDITIONS", "CONSENTED_BACKUP_MODEL_ONLY",
                         agent_id, conditions=["session_scoped_transfer_consent",
                                               "existing_provider_host_allowlist",
                                               "configured_execution_and_cost_limits"])
    return _decision("ALLOW", "ROSTERED_BR_MODEL_DISPATCH", agent_id)
