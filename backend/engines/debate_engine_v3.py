"""
engines/debate_engine_v3.py — Parallel Cluster Engine with Devil's Advocate & Gates
═══════════════════════════════════════════════════════════════════════════════════════
Orchestrates the 5-cluster parallel execution + DA + three-tier human feedback gates.

EXECUTION FLOW:
  Round N:
    ┌─ C1 (Foundation)        ─┐
    ├─ C2 (Financial Risk)     ─┤  All parallel via asyncio.gather()
    ├─ C3 (Mitigation & Exit)  ─┤
    ├─ C4 (Compliance)         ─┤
    └─ C5 (Strategy)          ─┘
              │
              ▼
    Devil's Advocate (receives ALL cluster summaries)
              │
              ▼
    Master Manager (Passo 11 + gate routing)
              │
              ▼
    Gate evaluation → Human review (if triggered) → Final synthesis
"""

import asyncio
import json
import re
import time
from collections import deque
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from crewai import Agent, Crew, LLM, Task

from config import settings
from agents.cluster_definitions import (
    CLUSTERS,
    DEVILS_ADVOCATE,
    MASTER_MANAGER,
    get_cluster_analysis_prompt,
    get_cluster_manager_prompt,
    get_devils_advocate_prompt,
    get_feedback_agent_config,
    get_feedback_routing_prompt,
    get_intracluster_vote_prompt,
    get_master_manager_prompt,
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


def weighted_median(scores_with_confidence: List[Tuple[float, int]]) -> float:
    """
    Compute weighted median of (score, confidence) pairs.
    Sort by confidence descending, take median of scores.
    """
    if not scores_with_confidence:
        return 5.0
    sorted_pairs = sorted(scores_with_confidence, key=lambda x: x[1], reverse=True)
    n = len(sorted_pairs)
    if n % 2 == 1:
        return sorted_pairs[n // 2][0]
    return (sorted_pairs[n // 2 - 1][0] + sorted_pairs[n // 2][0]) / 2


def confidence_aggregate(confidences: List[int]) -> float:
    """Average confidence across agents."""
    if not confidences:
        return 3.0
    return round(sum(confidences) / len(confidences), 1)


# ─────────────────────────────────────────────
#  GATE EVALUATOR
# ─────────────────────────────────────────────

class GateEvaluator:
    """Evaluates and tracks three-tier human feedback gates."""

    def __init__(self):
        self.gate_records: List[Dict] = []
        self.pending_gates: List[Dict] = []

    def evaluate(
        self,
        cluster_summaries: Dict[str, Dict],
        devil_advocate_output: Optional[Dict],
        master_synthesis: Dict,
    ) -> List[Dict]:
        """
        Determine which gates to trigger.
        Returns list of gate trigger dicts.
        """
        triggers = []

        # Gate 1: Low confidence in any cluster
        for cid, summary in cluster_summaries.items():
            parsed = summary.get("parsed", {})
            conf = parsed.get("confidence_aggregate", 5.0)
            if conf < settings.GATE_1_CONFIDENCE_THRESHOLD:
                triggers.append({
                    "gate_number": 1,
                    "trigger_type": "low_confidence",
                    "trigger_value": conf,
                    "threshold": settings.GATE_1_CONFIDENCE_THRESHOLD,
                    "affected_cluster": cid,
                    "description": (
                        f"Cluster '{CLUSTERS.get(cid, {}).get('name', cid)}' "
                        f"has confidence {conf} below threshold "
                        f"{settings.GATE_1_CONFIDENCE_THRESHOLD}"
                    ),
                })

        # Gate 2: Devil's Advocate gap severity + SAD score
        if devil_advocate_output:
            da_parsed = devil_advocate_output.get("parsed", {})
            gap_score = da_parsed.get("gap_severity_score", 0)
            sad_score = da_parsed.get("sad_score", 0)

            # Trigger based on gap severity score
            if gap_score > settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD:
                triggers.append({
                    "gate_number": 2,
                    "trigger_type": "devil_advocate",
                    "trigger_value": gap_score,
                    "threshold": settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD,
                    "affected_cluster": None,
                    "description": (
                        f"Analista Adversarial identificou lacunas com severidade "
                        f"{gap_score} acima do limiar {settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD}. "
                        f"SAD Score: {sad_score}/5"
                    ),
                    "brazilian_context": (
                        f"Foram detectadas premissas não declaradas, vieses cognitivos e/ou "
                        f"riscos regulatórios no contexto brasileiro. "
                        f"Perguntas não formuladas: {len(da_parsed.get('unasked_questions', []))}"
                    ),
                })

            # Also trigger if SAD score is critically high (>= 4)
            if sad_score >= 4:
                triggers.append({
                    "gate_number": 2,
                    "trigger_type": "sad_score",
                    "trigger_value": sad_score,
                    "threshold": 4.0,
                    "affected_cluster": None,
                    "description": (
                        f"Score do Advogado do Diabo (SAD) = {sad_score}/5 — "
                        f"lacunas críticas identificadas exigem revisão independente."
                    ),
                    "brazilian_context": (
                        f"Análise adversarial identificou riscos sistêmicos no contexto "
                        f"jurídico brasileiro que exigem atenção do comitê de risco."
                    ),
                })

        # Gate 3: Crítico classification
        master_parsed = master_synthesis.get("parsed", {})
        classification = master_parsed.get("final_classification", "")
        if classification == "Crítico" and settings.GATE_3_ALWAYS_FOR_CRITICO:
            triggers.append({
                "gate_number": 3,
                "trigger_type": "critico_classification",
                "trigger_value": master_parsed.get("final_score", 0),
                "threshold": 8.0,
                "affected_cluster": None,
                "description": (
                    f"Final classification is Crítico "
                    f"(score {master_parsed.get('final_score', 'N/A')})"
                ),
            })

        return triggers

    def record_trigger(self, trigger: Dict) -> Dict:
        """Record a triggered gate."""
        record = {
            "gate_number": trigger["gate_number"],
            "trigger": trigger,
            "status": "pending",
            "human_decision": None,
            "resolution": None,
            "timestamp_triggered": _ts(),
            "timestamp_resolved": None,
        }
        self.gate_records.append(record)
        self.pending_gates.append(record)
        return record

    def resolve_gate(
        self,
        gate_number: int,
        decision: str,
        reasoning: str,
        human_review_id: str,
        override_score: Optional[float] = None,
        override_classification: Optional[str] = None,
    ) -> Optional[Dict]:
        """Resolve a pending gate with human expert decision."""
        for record in self.pending_gates:
            if record["gate_number"] == gate_number:
                record["status"] = {
                    "approve": "approved",
                    "override": "overridden",
                    "request_reanalysis": "reanalysis_requested",
                }.get(decision, "pending")
                record["human_decision"] = {
                    "decision": decision,
                    "reasoning": reasoning,
                    "human_review_id": human_review_id,
                    "override_score": override_score,
                    "override_classification": override_classification,
                }
                record["timestamp_resolved"] = _ts()
                self.pending_gates.remove(record)
                return record
        return None

    def has_pending_gates(self) -> bool:
        return len(self.pending_gates) > 0

    def get_pending_gate_numbers(self) -> List[int]:
        return [g["gate_number"] for g in self.pending_gates]


# ─────────────────────────────────────────────
#  DEBATE ENGINE v3 — Parallel + DA + Gates
# ─────────────────────────────────────────────

class DebateEngineV3:
    """
    Parallel cluster execution engine with Devil's Advocate and three-tier gates.

    Public interface compatible with main.py.
    """

    def __init__(
        self,
        session_id: str,
        num_agents: int,
        num_rounds: int,
        workflow_type: str,
    ):
        self.session_id = session_id
        self.num_rounds = max(1, min(num_rounds, settings.MAX_ROUNDS))
        self.workflow_type = workflow_type
        self.current_round = 0

        # State
        self.cluster_summaries: Dict[str, Dict] = {}
        self.devil_advocate_output: Optional[Dict] = None
        self.master_summaries: List[Dict] = []
        self.feedback_agents: Dict[str, List[Dict]] = {k: [] for k in CLUSTERS}
        self.gate_evaluator = GateEvaluator()
        self.execution_metrics: Dict[str, Any] = {
            "total_latency_ms": 0,
            "cluster_latencies": {},
            "token_usage": {},
            "rounds": [],
        }

        # LLM
        self.llm = LLM(
            model=f"openai/{settings.MARITACA_MODEL}",
            base_url=settings.MARITACA_BASE_URL,
            api_key=settings.MARITACA_API_KEY,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
        )

        # Event queue for SSE
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

        # One shared gate smooths all cluster, adversarial, and synthesis calls.
        self._llm_call_semaphore = asyncio.Semaphore(
            max(1, settings.LLM_MAX_CONCURRENT_CALLS)
        )
        self._llm_start_lock = asyncio.Lock()
        self._llm_next_start_at = 0.0
        self._llm_input_reservations = deque()

    # ── Event helpers ────────────────────────

    @staticmethod
    def _evt(event_type: str, **kwargs) -> Dict:
        return {"type": event_type, "timestamp": _ts(), **kwargs}

    async def _emit(self, event: Dict):
        """Emit event to queue."""
        await self._event_queue.put(event)

    # ── Single agent execution ───────────────

    async def _run_agent(self, agent_cfg: Dict, prompt: str) -> str:
        """Run one agent through a bounded, paced provider-call queue."""
        async with self._llm_call_semaphore:
            # Approximate input tokens conservatively from prompt size.
            estimated_input_tokens = max(1, (len(prompt) + 2) // 3)
            async with self._llm_start_lock:
                while True:
                    now = time.monotonic()
                    while (
                        self._llm_input_reservations
                        and self._llm_input_reservations[0][0] <= now - 60
                    ):
                        self._llm_input_reservations.popleft()

                    used_tokens = sum(
                        tokens for _, tokens in self._llm_input_reservations
                    )
                    budget = max(1, settings.LLM_INPUT_TOKENS_PER_MINUTE)
                    pacing_wait = max(0.0, self._llm_next_start_at - now)
                    token_wait = 0.0
                    if (
                        self._llm_input_reservations
                        and used_tokens + estimated_input_tokens > budget
                    ):
                        token_wait = max(
                            0.0,
                            self._llm_input_reservations[0][0] + 60 - now,
                        )

                    wait_seconds = max(pacing_wait, token_wait)
                    if wait_seconds <= 0:
                        break
                    await asyncio.sleep(wait_seconds)

                started_at = time.monotonic()
                self._llm_input_reservations.append(
                    (started_at, estimated_input_tokens)
                )
                interval = max(0.0, settings.LLM_MIN_REQUEST_INTERVAL_SECONDS)
                self._llm_next_start_at = started_at + interval

            return await asyncio.to_thread(_run_crew, agent_cfg, prompt, self.llm)

    # ── Cluster execution (single cluster) ───

    async def _run_single_cluster(
        self,
        cluster_id: str,
        cluster: Dict,
        document_text: str,
        round_num: int,
    ) -> Dict:
        """Run a single cluster: analysis → voting → manager synthesis."""

        start_time = time.time()
        events = []

        # Phase 1: Analysis
        await self._emit(self._evt(
            "CLUSTER_START",
            cluster=cluster_id,
            cluster_name=cluster["name"],
            passos=cluster["passos"],
            agent_count=len(cluster["agents"]) + len(self.feedback_agents.get(cluster_id, [])),
            round=round_num,
        ))

        await self._emit(self._evt(
            "PHASE_START", phase="analysis", cluster=cluster_id, round=round_num
        ))

        all_agents = cluster["agents"] + self.feedback_agents.get(cluster_id, [])
        analyses = []

        for agent_cfg in all_agents:
            await self._emit(self._evt(
                "AGENT_THINKING",
                agent=agent_cfg["role"],
                cluster=cluster_id,
                cluster_name=cluster["name"],
                round=round_num,
            ))

            prompt = get_cluster_analysis_prompt(
                document_text=document_text,
                agent_cfg=agent_cfg,
                round_num=round_num,
                prior_cluster_summaries={},
                previous_analyses=None,
            )

            raw = await self._run_agent(agent_cfg, prompt)
            parsed = _safe_json(raw)

            analysis = {
                "agent": agent_cfg["role"],
                "content": raw,
                "parsed": parsed,
                "round": round_num,
                "cluster": cluster_id,
            }
            analyses.append(analysis)

            await self._emit(self._evt(
                "AGENT_ANALYSIS_COMPLETE",
                agent=agent_cfg["role"],
                cluster=cluster_id,
                cluster_name=cluster["name"],
                content=raw,
                parsed=parsed,
                round=round_num,
            ))

        # Phase 2: Voting
        await self._emit(self._evt(
            "PHASE_START", phase="voting", cluster=cluster_id, round=round_num
        ))

        all_scores: Dict[str, Any] = {}
        for i, agent_cfg in enumerate(all_agents):
            peers = [a for a in analyses if a["agent"] != agent_cfg["role"]]
            if not peers:
                continue

            await self._emit(self._evt(
                "AGENT_VOTING",
                agent=agent_cfg["role"],
                cluster=cluster_id,
                cluster_name=cluster["name"],
                round=round_num,
            ))

            prompt = get_intracluster_vote_prompt(
                my_analysis=analyses[i]["content"] if i < len(analyses) else "",
                peer_analyses=peers,
                cluster_name=cluster["name"],
            )

            raw = await self._run_agent(agent_cfg, prompt)
            parsed = _safe_json(raw)
            all_scores[agent_cfg["role"]] = {"raw": raw, "parsed": parsed}

            await self._emit(self._evt(
                "AGENT_VOTE_CAST",
                voter=agent_cfg["role"],
                cluster=cluster_id,
                cluster_name=cluster["name"],
                scores=parsed,
                round=round_num,
            ))

        # Phase 3: Manager synthesis
        await self._emit(self._evt(
            "PHASE_START", phase="synthesis", cluster=cluster_id, round=round_num
        ))

        prompt = get_cluster_manager_prompt(
            cluster=cluster,
            analyses=analyses,
            votes=all_scores,
            round_num=round_num,
            prior_cluster_summaries={},
        )

        raw = await self._run_agent(cluster["manager"], prompt)
        parsed = _safe_json(raw)

        cluster_summary = {"raw": raw, "parsed": parsed}

        elapsed = (time.time() - start_time) * 1000
        self.execution_metrics["cluster_latencies"][cluster_id] = round(elapsed, 1)

        await self._emit(self._evt(
            "CLUSTER_COMPLETE",
            cluster=cluster_id,
            cluster_name=cluster["name"],
            summary=parsed,
            round=round_num,
            latency_ms=round(elapsed, 1),
        ))

        return cluster_summary

    # ── Devil's Advocate ─────────────────────

    async def _run_devils_advocate(
        self,
        document_text: str,
        round_num: int,
    ) -> Dict:
        """Run Devil's Advocate with all cluster summaries as context."""

        await self._emit(self._evt(
            "DEVILS_ADVOCATE_START",
            round=round_num,
            context_clusters=list(self.cluster_summaries.keys()),
        ))

        prompt = get_devils_advocate_prompt(
            cluster_summaries=self.cluster_summaries,
            document_text=document_text,
            round_num=round_num,
        )

        raw = await self._run_agent(DEVILS_ADVOCATE, prompt)
        parsed = _safe_json(raw)

        self.devil_advocate_output = {"raw": raw, "parsed": parsed}

        await self._emit(self._evt(
            "DEVILS_ADVOCATE_COMPLETE",
            sad_score=parsed.get("sad_score", 0),
            gap_severity_score=parsed.get("gap_severity_score", 0),
            identified_gaps=parsed.get("identified_gaps", []),
            unstated_assumptions=parsed.get("unstated_assumptions", []),
            weak_points=parsed.get("weak_points", []),
            cognitive_biases_detected=parsed.get("cognitive_biases_detected", []),
            unasked_questions=parsed.get("unasked_questions", []),
            follow_up_actions=parsed.get("follow_up_actions", []),
            round=round_num,
        ))

        return self.devil_advocate_output

    # ── Master Manager ───────────────────────

    async def _run_master_manager(self, round_num: int) -> Dict:
        """Run Master Manager synthesis."""

        await self._emit(self._evt("MASTER_MANAGER_START", round=round_num))

        prompt = get_master_manager_prompt(
            cluster_summaries=self.cluster_summaries,
            devil_advocate_output=self.devil_advocate_output,
            round_num=round_num,
        )

        raw = await self._run_agent(MASTER_MANAGER, prompt)
        parsed = _safe_json(raw)

        master_summary = {"raw": raw, "parsed": parsed}
        self.master_summaries.append(master_summary)

        await self._emit(self._evt(
            "MASTER_MANAGER_COMPLETE",
            summary=parsed,
            round=round_num,
        ))

        return master_summary

    # ── Gate handling ────────────────────────

    async def _evaluate_and_trigger_gates(self, round_num: int) -> List[Dict]:
        """Evaluate gates and emit trigger events."""
        if not self.master_summaries:
            return []

        triggers = self.gate_evaluator.evaluate(
            cluster_summaries=self.cluster_summaries,
            devil_advocate_output=self.devil_advocate_output,
            master_synthesis=self.master_summaries[-1],
        )

        for trigger in triggers:
            record = self.gate_evaluator.record_trigger(trigger)
            await self._emit(self._evt(
                "GATE_TRIGGERED",
                gate_number=trigger["gate_number"],
                trigger=trigger,
                record=record,
                round=round_num,
            ))

        return triggers

    # ── Main debate flow ─────────────────────

    async def run_debate(
        self,
        document_text: str,
    ) -> AsyncGenerator[Dict, None]:
        """Stream debate events as they occur while the run executes."""
        execution = asyncio.create_task(self._execute_debate(document_text))
        execution.add_done_callback(lambda _: self._event_queue.put_nowait(None))

        try:
            while True:
                event = await self._event_queue.get()
                if event is None:
                    break
                yield event
            await execution
        except BaseException:
            if not execution.done():
                execution.cancel()
            raise

    async def _execute_debate(self, document_text: str) -> None:
        """Execute parallel clusters → Devil's Advocate → synthesis → gates."""

        total_start = time.time()
        self._running = True

        await self._emit(self._evt(
            "DEBATE_START",
            architecture="cluster_v3_parallel",
            total_clusters=len(CLUSTERS),
            total_agents=sum(len(c["agents"]) for c in CLUSTERS.values()) + 1,
            num_rounds=self.num_rounds,
            workflow_type=self.workflow_type,
            execution_mode="parallel",
        ))

        for round_num in range(1, self.num_rounds + 1):
            self.current_round = round_num
            round_start = time.time()

            await self._emit(self._evt(
                "ROUND_START",
                round=round_num,
                total_rounds=self.num_rounds,
            ))

            # Run all clusters in parallel
            cluster_tasks = [
                self._run_single_cluster(cid, cluster, document_text, round_num)
                for cid, cluster in CLUSTERS.items()
                if cid in settings.active_clusters_list
            ]

            cluster_results = await asyncio.gather(*cluster_tasks, return_exceptions=True)

            # Store summaries
            for i, (cid, _) in enumerate(
                [(cid, c) for cid, c in CLUSTERS.items() if cid in settings.active_clusters_list]
            ):
                result = cluster_results[i]
                if isinstance(result, Exception):
                    await self._emit(self._evt(
                        "ERROR",
                        message=f"Cluster {cid} failed: {str(result)}",
                        cluster=cid,
                        round=round_num,
                    ))
                else:
                    self.cluster_summaries[cid] = result

            # Devil's Advocate
            await self._run_devils_advocate(document_text, round_num)

            # Master Manager
            await self._run_master_manager(round_num)

            # Evaluate gates
            triggers = await self._evaluate_and_trigger_gates(round_num)

            round_elapsed = (time.time() - round_start) * 1000
            self.execution_metrics["rounds"].append({
                "round": round_num,
                "latency_ms": round(round_elapsed, 1),
                "gates_triggered": [t["gate_number"] for t in triggers],
            })

            await self._emit(self._evt(
                "ROUND_COMPLETE",
                round=round_num,
                summary=self.master_summaries[-1]["parsed"] if self.master_summaries else {},
                gates_triggered=[t["gate_number"] for t in triggers],
                latency_ms=round(round_elapsed, 1),
            ))

            # If gates are pending, pause and wait for human decisions
            if self.gate_evaluator.has_pending_gates():
                await self._emit(self._evt(
                    "AWAITING_GATE_DECISION",
                    pending_gates=self.gate_evaluator.get_pending_gate_numbers(),
                    round=round_num,
                ))

                # Wait for all gates to be resolved (checked via polling)
                while self.gate_evaluator.has_pending_gates():
                    await asyncio.sleep(0.5)

                await self._emit(self._evt(
                    "ALL_GATES_RESOLVED",
                    gate_records=self.gate_evaluator.gate_records,
                    round=round_num,
                ))

        total_elapsed = (time.time() - total_start) * 1000
        self.execution_metrics["total_latency_ms"] = round(total_elapsed, 1)

        await self._emit(self._evt(
            "DEBATE_COMPLETE",
            total_rounds=self.num_rounds,
            total_clusters_run=len(CLUSTERS) * self.num_rounds,
            total_agents_run=(sum(len(c["agents"]) for c in CLUSTERS.values()) + 1) * self.num_rounds,
            execution_metrics=self.execution_metrics,
            gate_records=self.gate_evaluator.gate_records,
            message="Analysis complete. Awaiting user feedback.",
        ))

        self._running = False


    async def process_feedback(
        self,
        feedback: str,
        document_text: str,
    ) -> AsyncGenerator[Dict, None]:
        """Stream feedback re-analysis events as they occur."""
        execution = asyncio.create_task(
            self._execute_process_feedback(feedback, document_text)
        )
        execution.add_done_callback(lambda _: self._event_queue.put_nowait(None))

        try:
            while True:
                event = await self._event_queue.get()
                if event is None:
                    break
                yield event
            await execution
        except BaseException:
            if not execution.done():
                execution.cancel()
            raise

    async def _execute_process_feedback(self, feedback: str, document_text: str) -> None:
        """Process user feedback with cluster re-routing."""

        new_round = self.current_round + 1
        self.current_round = new_round

        await self._emit(self._evt(
            "FEEDBACK_RECEIVED",
            feedback=feedback[:300],
            round=new_round,
        ))

        # Route feedback
        await self._emit(self._evt("FEEDBACK_ROUTING_START", round=new_round))

        routing_prompt = get_feedback_routing_prompt(
            feedback=feedback,
            cluster_summaries=self.cluster_summaries,
        )
        routing_raw = await self._run_agent(MASTER_MANAGER, routing_prompt)
        routing = _safe_json(routing_raw)
        target_cluster_id = routing.get("target_cluster", "strategy")

        await self._emit(self._evt(
            "FEEDBACK_ROUTED",
            target_cluster=target_cluster_id,
            target_cluster_name=CLUSTERS.get(target_cluster_id, {}).get("name", target_cluster_id),
            rationale=routing.get("rationale", ""),
            round=new_round,
        ))

        # Inject feedback agent
        feedback_agent = get_feedback_agent_config(feedback, target_cluster_id, new_round)
        self.feedback_agents[target_cluster_id].append(feedback_agent)

        await self._emit(self._evt(
            "FEEDBACK_AGENT_CREATED",
            agent=feedback_agent["role"],
            cluster=target_cluster_id,
            round=new_round,
        ))

        # Re-run target cluster + strategy cluster in parallel
        tasks = []
        if target_cluster_id in CLUSTERS:
            tasks.append(
                self._run_single_cluster(
                    target_cluster_id,
                    CLUSTERS[target_cluster_id],
                    document_text,
                    new_round,
                )
            )
        if target_cluster_id != "strategy" and "strategy" in CLUSTERS:
            tasks.append(
                self._run_single_cluster(
                    "strategy",
                    CLUSTERS["strategy"],
                    document_text,
                    new_round,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update summaries
        cluster_ids = [target_cluster_id]
        if target_cluster_id != "strategy":
            cluster_ids.append("strategy")

        for i, cid in enumerate(cluster_ids):
            if i < len(results) and not isinstance(results[i], Exception):
                self.cluster_summaries[cid] = results[i]

        # Re-run DA and Master
        await self._run_devils_advocate(document_text, new_round)
        await self._run_master_manager(new_round)

        # Re-evaluate gates
        triggers = await self._evaluate_and_trigger_gates(new_round)

        await self._emit(self._evt(
            "ROUND_COMPLETE",
            round=new_round,
            summary=self.master_summaries[-1]["parsed"] if self.master_summaries else {},
            gates_triggered=[t["gate_number"] for t in triggers],
        ))

        if self.gate_evaluator.has_pending_gates():
            await self._emit(self._evt(
                "AWAITING_GATE_DECISION",
                pending_gates=self.gate_evaluator.get_pending_gate_numbers(),
                round=new_round,
            ))
            while self.gate_evaluator.has_pending_gates():
                await asyncio.sleep(0.5)

        await self._emit(self._evt(
            "DEBATE_COMPLETE",
            total_rounds=new_round,
            gate_records=self.gate_evaluator.gate_records,
            message="Feedback incorporated. Analysis updated.",
        ))


    # ── Gate decision API ────────────────────

    def submit_gate_decision(
        self,
        gate_number: int,
        decision: str,
        reasoning: str,
        human_review_id: str,
        override_score: Optional[float] = None,
        override_classification: Optional[str] = None,
    ) -> Optional[Dict]:
        """Submit human expert decision for a gate."""
        return self.gate_evaluator.resolve_gate(
            gate_number=gate_number,
            decision=decision,
            reasoning=reasoning,
            human_review_id=human_review_id,
            override_score=override_score,
            override_classification=override_classification,
        )

    def get_pending_gates(self) -> List[Dict]:
        """Get list of pending gates."""
        return self.gate_evaluator.pending_gates

    def get_all_gate_records(self) -> List[Dict]:
        """Get all gate records."""
        return self.gate_evaluator.gate_records

    def get_metrics(self) -> Dict:
        """Get execution metrics."""
        return self.execution_metrics
