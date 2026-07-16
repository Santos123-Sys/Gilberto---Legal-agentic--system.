from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class WorkflowType(str, Enum):
    CONTRACT_REVIEW = "contract_review"
    CORPORATE_GOVERNANCE = "corporate_governance"
    COMPLIANCE_CHECK = "compliance_check"
    FULL_ANALYSIS = "full_analysis"


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_FEEDBACK = "awaiting_feedback"
    COMPLETED = "completed"
    ERROR = "error"


class SessionCreateRequest(BaseModel):
    num_agents: int = Field(default=3, ge=2, le=5, description="Number of debate agents")
    num_rounds: int = Field(default=2, ge=1, le=5, description="Number of debate rounds")
    workflow_type: WorkflowType = Field(
        default=WorkflowType.FULL_ANALYSIS,
        description="Type of legal analysis to perform"
    )


class SessionResponse(BaseModel):
    session_id: str
    status: str
    config: Dict[str, Any]


class FeedbackRequest(BaseModel):
    feedback: str = Field(..., min_length=10, description="User feedback on the analysis")
    accept_and_continue: bool = Field(
        default=False,
        description="Whether to accept current analysis and run one more round"
    )


class AgentAnalysis(BaseModel):
    agent_role: str
    content: str
    round_num: int
    confidence_score: Optional[float] = None


class RoundResult(BaseModel):
    round_num: int
    analyses: List[AgentAnalysis]
    scores: Dict[str, Any]
    summary: str


class DebateEvent(BaseModel):
    type: str
    timestamp: str
    data: Dict[str, Any] = {}
