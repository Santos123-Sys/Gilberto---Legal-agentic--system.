"""
models/schemas.py — Pydantic Request/Response Models
═══════════════════════════════════════════════════════════════════════
Defines all API contracts for the Gilberto Legal Agent system.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
#  ENUMS
# ─────────────────────────────────────────────

class RiskClassification(str, Enum):
    CRITICO = "Crítico"
    RELEVANTE = "Relevante"
    ACEITAVEL = "Aceitável"


class ConfidenceLevel(int, Enum):
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5


class WorkflowType(str, Enum):
    CONTRACT_REVIEW = "contract_review"
    NEGOTIATION = "negotiation"
    GOVERNANCE = "governance"
    REGULATORY = "regulatory"
    GENERAL = "general"


class GateDecision(str, Enum):
    APPROVE = "approve"
    OVERRIDE = "override"
    REQUEST_REANALYSIS = "request_reanalysis"


class GateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    OVERRIDDEN = "overridden"
    REANALYSIS_REQUESTED = "reanalysis_requested"
    SKIPPED = "skipped"


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_GATE = "awaiting_gate"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETED = "completed"
    ERROR = "error"


# ─────────────────────────────────────────────
#  AGENT OUTPUT SCHEMA
# ─────────────────────────────────────────────

class AgentFinding(BaseModel):
    item: str
    status: Literal["OK", "WARNING", "VIOLATION", "INFO"]
    evidence: Optional[str] = None
    legal_basis: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"


class RiskFlag(BaseModel):
    type: Literal["LEGAL", "FINANCIAL", "OPERATIONAL", "COMPLIANCE", "REPUTATIONAL"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    description: str
    mitigation: Optional[str] = None


class AgentAnalysis(BaseModel):
    """Standardized output every agent must produce."""
    agent: str
    cluster: str
    step: Optional[int] = None
    score: float = Field(ge=0, le=10, description="Numerical risk score 0-10")
    reasoning: str
    confidence_level: int = Field(ge=1, le=5)
    supporting_evidence: List[str] = Field(default_factory=list)
    recommended_classification: RiskClassification = RiskClassification.RELEVANTE
    key_findings: List[AgentFinding] = Field(default_factory=list)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class VoteResult(BaseModel):
    """Result of intra-cluster voting."""
    voter: str
    cluster: str
    scores: Dict[str, float] = Field(default_factory=dict)
    confidence_scores: Dict[str, int] = Field(default_factory=dict)
    rationale: str = ""


class ClusterSummary(BaseModel):
    """Cluster Manager synthesis output."""
    cluster: str
    cluster_name: str
    aggregated_score: float = Field(ge=0, le=10)
    confidence_aggregate: float = Field(ge=1, le=5)
    classification: RiskClassification
    summary: str
    key_findings: List[str] = Field(default_factory=list)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    agent_count: int = 0
    dissent_notes: Optional[str] = None


class DevilAdvocateOutput(BaseModel):
    """Devil's Advocate gap analysis with Brazilian context and SAD score."""
    sad_score: float = Field(ge=1, le=5, description="Score do Advogado do Diabo (1-5)")
    gap_severity_score: float = Field(ge=0, le=10)
    identified_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    unstated_assumptions: List[str] = Field(default_factory=list)
    weak_points: List[str] = Field(default_factory=list)
    cognitive_biases_detected: List[str] = Field(default_factory=list)
    unasked_questions: List[str] = Field(default_factory=list)
    follow_up_actions: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    overall_assessment: str = ""


class MasterSynthesis(BaseModel):
    """Final Master Manager output."""
    final_score: float = Field(ge=0, le=10)
    final_classification: RiskClassification
    confidence: float = Field(ge=1, le=5)
    reasoning: str
    cluster_summaries: Dict[str, ClusterSummary] = Field(default_factory=dict)
    devil_advocate_findings: Optional[DevilAdvocateOutput] = None
    executive_summary: str = ""
    critical_actions: List[str] = Field(default_factory=list)
    approval_checklist: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
#  GATE MODELS
# ─────────────────────────────────────────────

class GateTrigger(BaseModel):
    """Why a gate was triggered."""
    gate_number: int
    trigger_type: str  # "low_confidence" | "devil_advocate" | "critico_classification" | "sad_score"
    trigger_value: float
    threshold: float
    affected_cluster: Optional[str] = None
    description: str
    brazilian_context: Optional[str] = None


class GateDecisionRequest(BaseModel):
    """Human expert decision on a gate."""
    session_id: str
    gate_number: int
    human_review_id: str = Field(description="Identifier of the reviewing expert")
    decision: GateDecision
    reasoning: str = Field(description="Detailed expert reasoning")
    override_score: Optional[float] = Field(default=None, ge=0, le=10)
    override_classification: Optional[RiskClassification] = None


class GateRecord(BaseModel):
    """Full record of a gate interaction."""
    gate_number: int
    trigger: GateTrigger
    status: GateStatus = GateStatus.PENDING
    human_decision: Optional[GateDecisionRequest] = None
    resolution: Optional[str] = None
    timestamp_triggered: str = ""
    timestamp_resolved: Optional[str] = None


# ─────────────────────────────────────────────
#  SESSION MODELS
# ─────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    workflow_type: WorkflowType = WorkflowType.CONTRACT_REVIEW
    num_agents: int = 20
    num_rounds: int = 1
    document_type: Optional[str] = None
    jurisdiction: str = "BR"
    urgency: Literal["immediate", "high", "normal", "low"] = "normal"
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    config: Dict[str, Any]


class FeedbackRequest(BaseModel):
    feedback: str = Field(min_length=10, description="User feedback text")
    target_cluster: Optional[str] = None
    priority: Literal["low", "normal", "high"] = "normal"


class AnalysisResult(BaseModel):
    """Complete analysis result for a session."""
    session_id: str
    status: SessionStatus
    config: Dict[str, Any]
    cluster_results: Dict[str, ClusterSummary] = Field(default_factory=dict)
    devil_advocate: Optional[DevilAdvocateOutput] = None
    final_synthesis: Optional[MasterSynthesis] = None
    gate_records: List[GateRecord] = Field(default_factory=list)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    rounds_completed: int = 0


class SSEEvent(BaseModel):
    """Server-Sent Event wrapper."""
    type: str
    timestamp: str
    data: Dict[str, Any] = Field(default_factory=dict)
