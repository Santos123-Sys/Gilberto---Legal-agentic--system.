"""
gates/human_feedback.py — Three-Tier Human Feedback Gate System
═══════════════════════════════════════════════════════════════════════
Implements Gate 1 (low confidence), Gate 2 (Devil's Advocate gaps),
and Gate 3 (Crítico classification) with full state management.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

from config import settings


class GateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    OVERRIDDEN = "overridden"
    REANALYSIS_REQUESTED = "reanalysis_requested"
    SKIPPED = "skipped"


class GateType(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    DEVIL_ADVOCATE = "devil_advocate"
    CRITICO_CLASSIFICATION = "critico_classification"


class HumanFeedbackGate:
    """Represents a single human feedback gate instance."""

    def __init__(
        self,
        gate_number: int,
        gate_type: GateType,
        trigger_value: float,
        threshold: float,
        affected_cluster: Optional[str] = None,
        description: str = "",
    ):
        self.gate_number = gate_number
        self.gate_type = gate_type
        self.trigger_value = trigger_value
        self.threshold = threshold
        self.affected_cluster = affected_cluster
        self.description = description
        self.status = GateStatus.PENDING
        self.human_decision: Optional[Dict] = None
        self.resolution: Optional[str] = None
        self.timestamp_triggered = datetime.now().isoformat()
        self.timestamp_resolved: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "gate_number": self.gate_number,
            "gate_type": self.gate_type.value,
            "trigger_value": self.trigger_value,
            "threshold": self.threshold,
            "affected_cluster": self.affected_cluster,
            "description": self.description,
            "status": self.status.value,
            "human_decision": self.human_decision,
            "resolution": self.resolution,
            "timestamp_triggered": self.timestamp_triggered,
            "timestamp_resolved": self.timestamp_resolved,
        }

    def resolve(
        self,
        decision: str,
        reasoning: str,
        human_review_id: str,
        override_score: Optional[float] = None,
        override_classification: Optional[str] = None,
    ) -> Dict:
        """Resolve gate with human expert decision."""
        self.human_decision = {
            "decision": decision,
            "reasoning": reasoning,
            "human_review_id": human_review_id,
            "override_score": override_score,
            "override_classification": override_classification,
            "timestamp": datetime.now().isoformat(),
        }

        if decision == "approve":
            self.status = GateStatus.APPROVED
            self.resolution = "Human expert approved the analysis as-is."
        elif decision == "override":
            self.status = GateStatus.OVERRIDDEN
            self.resolution = (
                f"Human expert overrode score to {override_score}"
                if override_score is not None
                else "Human expert overrode the classification."
            )
        elif decision == "request_reanalysis":
            self.status = GateStatus.REANALYSIS_REQUESTED
            self.resolution = "Human expert requested re-analysis of affected components."
        else:
            self.status = GateStatus.SKIPPED
            self.resolution = "Gate was skipped."

        self.timestamp_resolved = datetime.now().isoformat()
        return self.to_dict()


class GateManager:
    """Manages all gates for a session."""

    def __init__(self):
        self.gates: List[HumanFeedbackGate] = []
        self._gate_counter = 0

    def check_and_create_gates(
        self,
        cluster_summaries: Dict[str, Dict],
        devil_advocate_output: Optional[Dict],
        master_synthesis: Dict,
    ) -> List[HumanFeedbackGate]:
        """Evaluate conditions and create gates as needed."""

        new_gates = []

        # Gate 1: Low confidence
        for cid, summary in cluster_summaries.items():
            parsed = summary.get("parsed", {})
            conf = parsed.get("confidence_aggregate", 5.0)
            if conf < settings.GATE_1_CONFIDENCE_THRESHOLD:
                gate = HumanFeedbackGate(
                    gate_number=1,
                    gate_type=GateType.LOW_CONFIDENCE,
                    trigger_value=conf,
                    threshold=settings.GATE_1_CONFIDENCE_THRESHOLD,
                    affected_cluster=cid,
                    description=f"Cluster {cid} confidence {conf} < {settings.GATE_1_CONFIDENCE_THRESHOLD}",
                )
                self.gates.append(gate)
                new_gates.append(gate)

        # Gate 2: Devil's Advocate
        if devil_advocate_output:
            da_parsed = devil_advocate_output.get("parsed", {})
            gap_score = da_parsed.get("gap_severity_score", 0)
            if gap_score > settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD:
                gate = HumanFeedbackGate(
                    gate_number=2,
                    gate_type=GateType.DEVIL_ADVOCATE,
                    trigger_value=gap_score,
                    threshold=settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD,
                    description=f"DA gap severity {gap_score} > {settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD}",
                )
                self.gates.append(gate)
                new_gates.append(gate)

        # Gate 3: Crítico
        master_parsed = master_synthesis.get("parsed", {})
        if master_parsed.get("final_classification") == "Crítico":
            gate = HumanFeedbackGate(
                gate_number=3,
                gate_type=GateType.CRITICO_CLASSIFICATION,
                trigger_value=master_parsed.get("final_score", 0),
                threshold=8.0,
                description=f"Final classification is Crítico",
            )
            self.gates.append(gate)
            new_gates.append(gate)

        return new_gates

    def get_pending_gates(self) -> List[HumanFeedbackGate]:
        return [g for g in self.gates if g.status == GateStatus.PENDING]

    def get_gate_by_number(self, gate_number: int) -> Optional[HumanFeedbackGate]:
        for g in self.gates:
            if g.gate_number == gate_number and g.status == GateStatus.PENDING:
                return g
        return None

    def resolve_gate(
        self,
        gate_number: int,
        decision: str,
        reasoning: str,
        human_review_id: str,
        override_score: Optional[float] = None,
        override_classification: Optional[str] = None,
    ) -> Optional[Dict]:
        gate = self.get_gate_by_number(gate_number)
        if gate:
            return gate.resolve(
                decision=decision,
                reasoning=reasoning,
                human_review_id=human_review_id,
                override_score=override_score,
                override_classification=override_classification,
            )
        return None

    def all_resolved(self) -> bool:
        return all(g.status != GateStatus.PENDING for g in self.gates)

    def to_list(self) -> List[Dict]:
        return [g.to_dict() for g in self.gates]
