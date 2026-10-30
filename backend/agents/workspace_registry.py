"""Presentation identities derived from the engine roster, never new legal agents.

Display names follow the (Portuguese) roster verbatim. IDs come from each
definition's stable ``key`` — the historical identifier — so translating or
renaming a role never changes an agent's ID in journals or checkpoints.
Definitions without a ``key`` (e.g. feedback agents in checkpoints saved
before keys existed) fall back to the slug of their recorded role, which is
how their IDs were always derived. Feedback identities include their round.
No prompt, weighting, or professional qualification is changed by this registry.
"""
import hashlib
import re

from agents.cluster_definitions import (
    CLUSTERS, DEVILS_ADVOCATE, MASTER_MANAGER, focused_reviewer_role,
)


STYLES = {
    "foundation": "Sistemático e preciso; verifica a completude do documento e o contexto.",
    "financial_risk": "Quantitativo e metódico; separa valores de conclusões jurídicas.",
    "mitigation_exit": "Orientado a cenários; examina obrigações e caminhos de saída disponíveis.",
    "compliance": "Meticuloso e cético; aponta afirmações de conformidade sem respaldo.",
    "strategy": "Crítico e pragmático; identifica contrapartidas e posições concorrentes.",
}


# Keyed by the stable agent key, never by the display name.
ROLE_STYLES = {
    "contract-classifier": "Classifica o tipo de operação e verifica a estrutura contratual.",
    "document-integrity-verifier": "Examina a coerência do documento e registros ausentes.",
    "party-qualification-analyst": "Verifica as partes, os poderes e os dados de identificação.",
    "transactional-context-mapper": "Mapeia o contexto comercial e as obrigações conexas.",
    "price-payment-analyst": "Confronta a mecânica de pagamento com as evidências documentais.",
    "penalty-clause-validator": "Testa a estrutura da cláusula penal diante das fontes brasileiras aplicáveis.",
    "guarantee-security-analyst": "Examina as garantias e as premissas de exequibilidade.",
    "economic-exposure-quantifier": "Quantifica cenários adversos separadamente das conclusões jurídicas.",
    "termination-rights-analyst": "Examina notificações, hipóteses de extinção e suas consequências.",
    "force-majeure-hardship-analyst": "Testa as premissas sobre eventos extraordinários e a alocação de riscos.",
    "dispute-resolution-analyst": "Examina as cláusulas de foro e de solução de controvérsias.",
    "exit-strategy-evaluator": "Mapeia opções de saída, condições e obrigações remanescentes.",
    "lgpd-data-protection-analyst": "Verifica as obrigações brasileiras de proteção de dados pessoais.",
    "anti-corruption-compliance-analyst": "Testa os controles de integridade e as disposições anticorrupção.",
    "electronic-signature-validator": "Examina a mecânica de assinatura e as ressalvas de validade jurídica.",
    "general-provisions-reviewer": "Audita a coerência das cláusulas gerais do contrato.",
    "negotiation-leverage-assessor": "Avalia o poder de negociação e as restrições documentadas.",
    "concession-boundary-optimizer": "Avalia contrapartidas e limites inegociáveis.",
    "counterparty-intent-analyst": "Questiona premissas sobre a intenção da contraparte.",
    "deal-structure-evaluator": "Compara estruturas contratuais e transacionais alternativas.",
}


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def identity(cluster_id, definition, kind="specialist"):
    role = definition["role"]
    key = definition.get("key") or _slug(role)
    stable_id = f"{cluster_id}:{kind}:{key}"
    return {
        "id": stable_id, "role": role, "display_name": role,
        "cluster_id": cluster_id, "kind": kind,
        "avatar_key": hashlib.sha256(stable_id.encode()).hexdigest()[:12],
        "specialization": definition.get("goal", ""),
        "working_style": (ROLE_STYLES.get(key, STYLES.get(cluster_id, "Integrador e focado em evidências."))
                          if kind not in ("adversarial", "orchestrator") else
                          ("Adversarial e crítico; contesta conclusões sem respaldo." if kind == "adversarial"
                           else "Integra os resultados validados das frentes e encaminha as revisões obrigatórias.")),
        "identity_notice": "Papel de IA; não representa um advogado inscrito na OAB.",
    }


def match_agent(cluster_roster, recorded_role):
    """Find the roster identity for a role name recorded in an event.

    Matches the current (Portuguese) display name, or — for events recorded
    before the translation — the historical English name, whose slug is the
    stable key embedded in the agent ID.
    """
    if not isinstance(recorded_role, str) or not recorded_role:
        return None
    members = cluster_roster["agents"] + [cluster_roster["manager"]]
    legacy_key = _slug(recorded_role)
    return (next((a for a in members if a["role"] == recorded_role), None)
            or next((a for a in members if a["id"].split(":", 2)[2] == legacy_key), None))


def roster_for_engine(engine, active_ids):
    roster = []
    for cid in active_ids:
        cluster = CLUSTERS[cid]
        definitions = cluster["agents"]
        if engine.review_depth == "focused":
            definitions = [{"role": focused_reviewer_role(cluster), "goal": cluster["description"],
                            "key": cluster["focused_key"]}]
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
