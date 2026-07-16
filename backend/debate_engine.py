"""
debate_engine.py — Cluster Architecture Engine
═══════════════════════════════════════════════════════════════════════
Orchestrates the 20-agent hierarchical cluster system.

EXECUTION FLOW (Sequential):
  Round N:
    Cluster 1 (Foundation)        → 4 agents analyze → intra-cluster vote → Cluster Manager 1
    Cluster 2 (Financial Risk)    → 4 agents analyze → intra-cluster vote → Cluster Manager 2
    Cluster 3 (Mitigation & Exit) → 4 agents analyze → intra-cluster vote → Cluster Manager 3
    Cluster 4 (Compliance)        → 4 agents analyze → intra-cluster vote → Cluster Manager 4
    Cluster 5 (Strategy)          → 4 agents analyze → intra-cluster vote → Cluster Manager 5
    Master Manager                → Passo 11 formula → Final synthesis → User

VOTING PRINCIPLE:
  Agents vote ONLY within their cluster (same domain knowledge).
  Cross-cluster synthesis happens ONLY at Cluster Manager level.
  Master Manager receives cluster summaries — never raw agent outputs.

FEEDBACK ROUTING:
  User feedback → Master Manager classifies → routes to correct cluster
  Feedback Advocate injected into target cluster
  That cluster re-runs → Cluster 5 re-runs adversarially → Master re-synthesizes
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from crewai import Agent, Task, Crew, LLM

from config import settings
from agents.cluster_definitions import (
    CLUSTERS,
    MASTER_MANAGER,
    get_cluster_analysis_prompt,
    get_intracluster_vote_prompt,
    get_cluster_manager_prompt,
    get_master_manager_prompt,
    get_feedback_routing_prompt,
    get_feedback_agent_config,
)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().isoformat()


def _safe_json(raw: str) -> Any:
    """Best-effort JSON extraction from an LLM response."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_content": raw}


def _run_crew(agent_cfg: Dict, prompt: str, llm: LLM) -> str:
    """Synchronous crew execution — called via asyncio.to_thread."""
    agent = Agent(
        role=agent_cfg["role"],
        goal=agent_cfg["goal"],
        backstory=agent_cfg["backstory"],
        llm=llm,
        verbose=False,
        max_iter=2,
        allow_delegation=False,
    )
    task = Task(
        description=prompt,
        expected_output="Valid JSON object",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    return crew.kickoff().raw


# ─────────────────────────────────────────────
#  DEBATE ENGINE (Cluster Architecture)
# ─────────────────────────────────────────────

class DebateEngine:
    """
    Public interface unchanged from v1 — main.py requires no changes.
    Internally orchestrates the full 20-agent cluster system.
    """

    def __init__(
        self,
        session_id: str,
        num_agents: int,       # kept for API compatibility — now always 20
        num_rounds: int,
        workflow_type: str,
    ):
        self.session_id = session_id
        self.num_rounds = max(1, min(num_rounds, settings.MAX_ROUNDS))
        self.workflow_type = workflow_type
        self.current_round = 0

        # Cluster state — accumulated across rounds
        self.cluster_summaries: Dict[str, Dict] = {}
        self.master_summaries: List[Dict] = []

        # Per-cluster feedback agents — injected when user submits feedback
        self.feedback_agents: Dict[str, List[Dict]] = {k: [] for k in CLUSTERS}

        # Maritaca via OpenAI-compatible interface
        self.llm = LLM(
            model=f"openai/{settings.MARITACA_MODEL}",
            base_url=settings.MARITACA_BASE_URL,
            api_key=settings.MARITACA_API_KEY,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

    # ── Event helpers ────────────────────────

    @staticmethod
    def _evt(event_type: str, **kwargs) -> Dict:
        return {"type": event_type, "timestamp": _ts(), **kwargs}

    # ── Single agent execution ───────────────

    async def _run_agent(self, agent_cfg: Dict, prompt: str) -> str:
        """Run one agent in a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(_run_crew, agent_cfg, prompt, self.llm)

    # ── Phase 1: Cluster analysis ────────────

    async def _run_cluster_analysis_phase(
        self,
        cluster: Dict,
        document_text: str,
        round_num: int,
        prior_cluster_summaries: Dict[str, str],
        previous_round_analyses: Optional[List[Dict]],
    ) -> AsyncGenerator[Dict, None]:
        """Each agent in the cluster independently analyzes the document."""

        all_agents = cluster["agents"] + self.feedback_agents.get(cluster["id"], [])
        analyses = []

        for agent_cfg in all_agents:
            yield self._evt(
                "AGENT_THINKING",
                agent=agent_cfg["role"],
                cluster=cluster["id"],
                cluster_name=cluster["name"],
                round=round_num,
            )

            prompt = get_cluster_analysis_prompt(
                document_text=document_text,
                agent_cfg=agent_cfg,
                round_num=round_num,
                prior_cluster_summaries={
                    k: v.get("raw", "") for k, v in prior_cluster_summaries.items()
                },
                previous_analyses=previous_round_analyses,
            )

            raw = await self._run_agent(agent_cfg, prompt)
            parsed = _safe_json(raw)

            analysis = {
                "agent": agent_cfg["role"],
                "content": raw,
                "parsed": parsed,
                "round": round_num,
                "cluster": cluster["id"],
            }
            analyses.append(analysis)

            yield self._evt(
                "AGENT_ANALYSIS_COMPLETE",
                agent=agent_cfg["role"],
                cluster=cluster["id"],
                cluster_name=cluster["name"],
                content=raw,
                parsed=parsed,
                round=round_num,
            )

        # Store on cluster for voting phase
        cluster["_current_analyses"] = analyses

    # ── Phase 2: Intra-cluster voting ────────

    async def _run_cluster_voting_phase(
        self,
        cluster: Dict,
        round_num: int,
    ) -> AsyncGenerator[Dict, None]:
        """Agents score ONLY peers within the same cluster."""

        analyses = cluster.get("_current_analyses", [])
        all_agents = cluster["agents"] + self.feedback_agents.get(cluster["id"], [])
        all_scores: Dict[str, Any] = {}

        for i, agent_cfg in enumerate(all_agents):
            # Only vote if there are peers
            peers = [a for a in analyses if a["agent"] != agent_cfg["role"]]
            if not peers:
                continue

            yield self._evt(
                "AGENT_VOTING",
                agent=agent_cfg["role"],
                cluster=cluster["id"],
                cluster_name=cluster["name"],
                round=round_num,
            )

            prompt = get_intracluster_vote_prompt(
                my_analysis=analyses[i]["content"] if i < len(analyses) else "",
                peer_analyses=peers,
                cluster_name=cluster["name"],
            )

            raw = await self._run_agent(agent_cfg, prompt)
            parsed = _safe_json(raw)

            all_scores[agent_cfg["role"]] = {"raw": raw, "parsed": parsed}

            yield self._evt(
                "AGENT_VOTE_CAST",
                voter=agent_cfg["role"],
                cluster=cluster["id"],
                cluster_name=cluster["name"],
                scores=parsed,
                round=round_num,
            )

        cluster["_current_scores"] = all_scores

    # ── Phase 3: Cluster manager synthesis ───

    async def _run_cluster_manager(
        self,
        cluster: Dict,
        round_num: int,
        prior_cluster_summaries: Dict[str, Dict],
    ) -> Dict:
        """Cluster manager synthesizes its 4 agents into a cluster summary."""

        prompt = get_cluster_manager_prompt(
            cluster=cluster,
            analyses=cluster.get("_current_analyses", []),
            votes=cluster.get("_current_scores", {}),
            round_num=round_num,
            prior_cluster_summaries={
                k: v.get("raw", "") for k, v in prior_cluster_summaries.items()
            },
        )

        raw = await self._run_agent(cluster["manager"], prompt)
        parsed = _safe_json(raw)

        return {"raw": raw, "parsed": parsed}

    # ── Master Manager ────────────────────────

    async def _run_master_manager(self, round_num: int) -> Dict:
        """Master Manager applies Passo 11 formula and produces final synthesis."""

        prompt = get_master_manager_prompt(
            cluster_summaries=self.cluster_summaries,
            round_num=round_num,
        )

        raw = await self._run_agent(MASTER_MANAGER, prompt)
        parsed = _safe_json(raw)

        return {"raw": raw, "parsed": parsed}

    # ── Full sequential cluster run ───────────

    async def _run_full_cluster_sequence(
        self,
        document_text: str,
        round_num: int,
        previous_round_data: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        Sequential execution: Cluster 1 → 2 → 3 → 4 → 5 → Master Manager.
        Each cluster receives summaries from all prior clusters.
        """
        completed_summaries: Dict[str, Dict] = {}

        for cluster_id, cluster in CLUSTERS.items():

            yield self._evt(
                "CLUSTER_START",
                cluster=cluster_id,
                cluster_name=cluster["name"],
                passos=cluster["passos"],
                agent_count=len(cluster["agents"]) + len(self.feedback_agents.get(cluster_id, [])),
                round=round_num,
            )

            # Get previous round analyses for this cluster (if round > 1)
            prev_analyses = None
            if previous_round_data and cluster_id in previous_round_data.get("clusters", {}):
                prev_analyses = previous_round_data["clusters"][cluster_id].get("analyses", [])

            # Phase 1: Analysis
            yield self._evt("PHASE_START", phase="analysis", cluster=cluster_id, round=round_num)
            async for evt in self._run_cluster_analysis_phase(
                cluster, document_text, round_num, completed_summaries, prev_analyses
            ):
                yield evt

            # Phase 2: Intra-cluster voting
            yield self._evt("PHASE_START", phase="voting", cluster=cluster_id, round=round_num)
            async for evt in self._run_cluster_voting_phase(cluster, round_num):
                yield evt

            # Phase 3: Cluster Manager synthesis
            yield self._evt("PHASE_START", phase="synthesis", cluster=cluster_id, round=round_num)
            cluster_summary = await self._run_cluster_manager(
                cluster, round_num, completed_summaries
            )

            # Store summary for downstream clusters
            completed_summaries[cluster_id] = cluster_summary
            self.cluster_summaries[cluster_id] = cluster_summary

            yield self._evt(
                "CLUSTER_COMPLETE",
                cluster=cluster_id,
                cluster_name=cluster["name"],
                summary=cluster_summary["parsed"],
                round=round_num,
            )

        # Master Manager — receives all 5 cluster summaries
        yield self._evt("MASTER_MANAGER_START", round=round_num)
        master_summary = await self._run_master_manager(round_num)
        self.master_summaries.append(master_summary)

        yield self._evt(
            "MASTER_MANAGER_COMPLETE",
            summary=master_summary["parsed"],
            round=round_num,
        )

        # Return full round data for next-round context
        self._last_round_data = {
            "round": round_num,
            "clusters": {
                cid: {
                    "analyses": CLUSTERS[cid].get("_current_analyses", []),
                    "scores": CLUSTERS[cid].get("_current_scores", {}),
                    "summary": completed_summaries.get(cid, {}),
                }
                for cid in CLUSTERS
            },
            "master_summary": master_summary,
        }

    # ── Public API (same interface as v1) ────

    async def run_debate(
        self,
        document_text: str,
    ) -> AsyncGenerator[Dict, None]:
        """
        Execute all debate rounds — sequential cluster architecture.
        Same external interface as v1 DebateEngine.
        """
        self._document_text = document_text

        yield self._evt(
            "DEBATE_START",
            architecture="cluster_v2",
            total_clusters=len(CLUSTERS),
            total_agents=sum(len(c["agents"]) for c in CLUSTERS.values()),
            num_rounds=self.num_rounds,
            workflow_type=self.workflow_type,
            execution_mode="sequential",
        )

        previous_round_data = None

        for round_num in range(1, self.num_rounds + 1):
            self.current_round = round_num

            yield self._evt(
                "ROUND_START",
                round=round_num,
                total_rounds=self.num_rounds,
            )

            async for evt in self._run_full_cluster_sequence(
                document_text, round_num, previous_round_data
            ):
                yield evt

            previous_round_data = getattr(self, "_last_round_data", None)

            yield self._evt(
                "ROUND_COMPLETE",
                round=round_num,
                summary=self.master_summaries[-1]["parsed"] if self.master_summaries else {},
                round_data=previous_round_data,
            )

        yield self._evt(
            "DEBATE_COMPLETE",
            total_rounds=self.num_rounds,
            total_clusters_run=len(CLUSTERS) * self.num_rounds,
            total_agents_run=sum(len(c["agents"]) for c in CLUSTERS.values()) * self.num_rounds,
            message="Analysis complete. Awaiting user feedback.",
        )

    async def process_feedback(
        self,
        feedback: str,
        document_text: str,
    ) -> AsyncGenerator[Dict, None]:
        """
        Route user feedback to the correct cluster.
        Run that cluster + Cluster 5 (adversarial) + Master Manager.
        """
        new_round = self.current_round + 1
        self.current_round = new_round

        yield self._evt(
            "FEEDBACK_RECEIVED",
            feedback=feedback[:300],
            round=new_round,
        )

        # Step 1: Master Manager routes feedback to target cluster
        yield self._evt("FEEDBACK_ROUTING_START", round=new_round)

        routing_prompt = get_feedback_routing_prompt(
            feedback=feedback,
            cluster_summaries=self.cluster_summaries,
        )
        routing_raw = await self._run_agent(MASTER_MANAGER, routing_prompt)
        routing = _safe_json(routing_raw)
        target_cluster_id = routing.get("target_cluster", "cluster_5")

        yield self._evt(
            "FEEDBACK_ROUTED",
            target_cluster=target_cluster_id,
            target_cluster_name=CLUSTERS.get(target_cluster_id, {}).get("name", target_cluster_id),
            rationale=routing.get("rationale", ""),
            round=new_round,
        )

        # Step 2: Inject Feedback Advocate into target cluster
        feedback_agent = get_feedback_agent_config(feedback, target_cluster_id, new_round)
        self.feedback_agents[target_cluster_id].append(feedback_agent)

        yield self._evt(
            "FEEDBACK_AGENT_CREATED",
            agent=feedback_agent["role"],
            cluster=target_cluster_id,
            round=new_round,
        )

        # Step 3: Re-run target cluster with Feedback Advocate
        target_cluster = CLUSTERS[target_cluster_id]
        completed_summaries = dict(self.cluster_summaries)

        yield self._evt("CLUSTER_START", cluster=target_cluster_id,
                       cluster_name=target_cluster["name"], round=new_round,
                       triggered_by="feedback")

        yield self._evt("PHASE_START", phase="analysis",
                       cluster=target_cluster_id, round=new_round)
        async for evt in self._run_cluster_analysis_phase(
            target_cluster, document_text, new_round, completed_summaries, None
        ):
            yield evt

        yield self._evt("PHASE_START", phase="voting",
                       cluster=target_cluster_id, round=new_round)
        async for evt in self._run_cluster_voting_phase(target_cluster, new_round):
            yield evt

        yield self._evt("PHASE_START", phase="synthesis",
                       cluster=target_cluster_id, round=new_round)
        updated_summary = await self._run_cluster_manager(
            target_cluster, new_round, completed_summaries
        )
        self.cluster_summaries[target_cluster_id] = updated_summary

        yield self._evt("CLUSTER_COMPLETE", cluster=target_cluster_id,
                       cluster_name=target_cluster["name"],
                       summary=updated_summary["parsed"], round=new_round)

        # Step 4: Re-run Cluster 5 (adversarial — always re-runs after any feedback)
        if target_cluster_id != "cluster_5":
            cluster_5 = CLUSTERS["cluster_5"]
            completed_summaries_for_5 = dict(self.cluster_summaries)

            yield self._evt("CLUSTER_START", cluster="cluster_5",
                           cluster_name="Strategy & Adversarial", round=new_round,
                           triggered_by="feedback_adversarial_rerun")

            yield self._evt("PHASE_START", phase="analysis",
                           cluster="cluster_5", round=new_round)
            async for evt in self._run_cluster_analysis_phase(
                cluster_5, document_text, new_round, completed_summaries_for_5, None
            ):
                yield evt

            yield self._evt("PHASE_START", phase="voting",
                           cluster="cluster_5", round=new_round)
            async for evt in self._run_cluster_voting_phase(cluster_5, new_round):
                yield evt

            yield self._evt("PHASE_START", phase="synthesis",
                           cluster="cluster_5", round=new_round)
            cluster_5_summary = await self._run_cluster_manager(
                cluster_5, new_round, completed_summaries_for_5
            )
            self.cluster_summaries["cluster_5"] = cluster_5_summary

            yield self._evt("CLUSTER_COMPLETE", cluster="cluster_5",
                           cluster_name="Strategy & Adversarial",
                           summary=cluster_5_summary["parsed"], round=new_round)

        # Step 5: Master Manager re-synthesizes with updated cluster summaries
        yield self._evt("MASTER_MANAGER_START", round=new_round, triggered_by="feedback")
        master_summary = await self._run_master_manager(new_round)
        self.master_summaries.append(master_summary)

        yield self._evt("MASTER_MANAGER_COMPLETE",
                       summary=master_summary["parsed"], round=new_round)

        yield self._evt(
            "ROUND_COMPLETE",
            round=new_round,
            summary=master_summary["parsed"],
            triggered_by="user_feedback",
        )

        yield self._evt(
            "DEBATE_COMPLETE",
            total_rounds=new_round,
            message="Feedback round complete. Awaiting further instructions.",
        )
