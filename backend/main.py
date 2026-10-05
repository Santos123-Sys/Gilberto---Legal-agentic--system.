"""
main.py — Gilberto Legal Agent API v3
═══════════════════════════════════════════════════════════════════════
FastAPI backend with parallel cluster execution, Devil's Advocate,
three-tier human feedback gates, and Agentic UI support.

Endpoints:
  POST   /api/sessions                      Create session
  POST   /api/sessions/{id}/start           Upload doc + start debate
  GET    /api/sessions/{id}/stream          SSE stream of debate events
  GET    /api/sessions/{id}/status          Current session status
  GET    /api/sessions/{id}/results         Full results after debate
  POST   /api/sessions/{id}/feedback        Submit user feedback
  POST   /api/sessions/{id}/gate-decision   Submit gate decision (human expert)
  GET    /api/sessions/{id}/gates           Get pending gate info
  POST   /api/sessions/{id}/accept          Mark session as complete
  GET    /api/health                        Health check
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from document_extractor import DocumentExtractionError, extract_document_text
from engines.debate_engine_v3 import DebateEngineV3
from models.schemas import (
    FeedbackRequest,
    GateDecisionRequest,
    SessionCreateRequest,
    SessionResponse,
)

# ─────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Gilberto Legal Agent API v3",
    description="Multi-agent AI debate system with parallel clusters, Devil's Advocate, and human feedback gates",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  IN-MEMORY SESSION STORE
# ─────────────────────────────────────────────

sessions: Dict[str, dict] = {}


def _get_session(session_id: str) -> dict:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


# ─────────────────────────────────────────────
#  BACKGROUND TASK RUNNERS
# ─────────────────────────────────────────────

async def _run_debate_bg(session_id: str, document_text: str):
    """Run debate in background, collecting events."""
    session = sessions[session_id]
    engine: DebateEngineV3 = session["engine"]

    try:
        # Collect events from the engine
        async for event in engine.run_debate(document_text):
            session["events"].append(event)

            if event["type"] == "ROUND_COMPLETE":
                session["rounds"].append({
                    "round": event.get("round"),
                    "summary": event.get("summary", {}),
                    "gates_triggered": event.get("gates_triggered", []),
                    "latency_ms": event.get("latency_ms", 0),
                })

            elif event["type"] == "GATE_TRIGGERED":
                session["status"] = "awaiting_gate"
                session["pending_gates"].append(event.get("gate_number"))

            elif event["type"] == "ALL_GATES_RESOLVED":
                session["pending_gates"] = []
                session["status"] = "awaiting_feedback"

            elif event["type"] == "DEBATE_COMPLETE":
                if not session["pending_gates"]:
                    session["status"] = "awaiting_feedback"
                session["execution_metrics"] = event.get("execution_metrics", {})
                session["gate_records"] = event.get("gate_records", [])

            elif event["type"] == "ERROR":
                session["status"] = "error"
                session["error"] = event.get("message", "Unknown error")

    except Exception as exc:
        session["events"].append({
            "type": "ERROR",
            "message": str(exc),
            "timestamp": datetime.now().isoformat(),
        })
        session["status"] = "error"
        session["error"] = str(exc)


async def _run_feedback_bg(session_id: str, feedback: str):
    """Process feedback in background."""
    session = sessions[session_id]
    engine: DebateEngineV3 = session["engine"]
    document_text: str = session.get("document_text", "")

    try:
        async for event in engine.process_feedback(feedback, document_text):
            session["events"].append(event)

            if event["type"] == "ROUND_COMPLETE":
                session["rounds"].append({
                    "round": event.get("round"),
                    "summary": event.get("summary", {}),
                    "gates_triggered": event.get("gates_triggered", []),
                })

            elif event["type"] == "GATE_TRIGGERED":
                session["status"] = "awaiting_gate"
                session["pending_gates"].append(event.get("gate_number"))

            elif event["type"] == "ALL_GATES_RESOLVED":
                session["pending_gates"] = []
                session["status"] = "awaiting_feedback"

            elif event["type"] == "DEBATE_COMPLETE":
                if not session["pending_gates"]:
                    session["status"] = "awaiting_feedback"

    except Exception as exc:
        session["events"].append({
            "type": "ERROR",
            "message": str(exc),
            "timestamp": datetime.now().isoformat(),
        })
        session["status"] = "error"
        session["error"] = str(exc)


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "architecture": "parallel_clusters_with_devils_advocate",
        "active_clusters": settings.active_clusters_list,
        "gate_thresholds": {
            "gate_1_confidence": settings.GATE_1_CONFIDENCE_THRESHOLD,
            "gate_2_da_severity": settings.GATE_2_DEVIL_ADVOCATE_THRESHOLD,
            "gate_2_sad_score": 4.0,
            "gate_3_critico": settings.GATE_3_ALWAYS_FOR_CRITICO,
        },
        "brazilian_context": {
            "norms_since_1988": "6M+",
            "pending_lawsuits": "80M+",
            "regulators": ["CVM", "BACEN", "ANPD", "ANS", "ANVISA", "CADE", "IBAMA", "ANEEL", "ANATEL"],
            "sad_score_enabled": True,
        },
    }


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new debate session with specified configuration."""
    session_id = str(uuid.uuid4())
    engine = DebateEngineV3(
        session_id=session_id,
        num_agents=request.num_agents,
        num_rounds=request.num_rounds,
        workflow_type=request.workflow_type.value if hasattr(request.workflow_type, 'value') else str(request.workflow_type),
    )

    sessions[session_id] = {
        "id": session_id,
        "engine": engine,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "config": request.model_dump(),
        "rounds": [],
        "events": [],
        "pending_gates": [],
        "gate_records": [],
        "execution_metrics": {},
        "document_text": None,
        "document_name": None,
        "error": None,
    }

    return SessionResponse(
        session_id=session_id,
        status="created",
        config=request.model_dump(),
    )


@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str, document: UploadFile = File(...)):
    """Upload the legal document and start the debate."""
    session = _get_session(session_id)

    if session["status"] != "created":
        raise HTTPException(status_code=400, detail="Session already started")

    content = await document.read()

    try:
        document_text = extract_document_text(document.filename or "", content)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session["document_text"] = document_text
    session["document_name"] = document.filename
    session["status"] = "running"

    asyncio.create_task(_run_debate_bg(session_id, document_text))

    return {
        "status": "started",
        "session_id": session_id,
        "filename": document.filename,
        "document_format": (document.filename or "").rsplit(".", 1)[-1].lower(),
        "extracted_characters": len(document_text),
        "architecture": "parallel_v3",
    }


@app.get("/api/sessions/{session_id}/stream")
async def stream_events(session_id: str, cursor: int = 0):
    """Server-Sent Events stream with cursor-based resume."""
    _get_session(session_id)

    async def generator():
        session = sessions[session_id]
        idx = cursor

        while True:
            events = session["events"]

            while idx < len(events):
                yield f"data: {json.dumps(events[idx])}\n\n"
                idx += 1

            if session["status"] in ("completed", "error"):
                yield f"data: {json.dumps({'type': 'STREAM_END', 'timestamp': datetime.now().isoformat()})}\n\n"
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/sessions/{session_id}/status")
async def get_status(session_id: str):
    """Get current session status."""
    session = _get_session(session_id)
    return {
        "session_id": session_id,
        "status": session["status"],
        "current_round": session["engine"].current_round,
        "total_rounds": session["config"]["num_rounds"],
        "events_count": len(session["events"]),
        "rounds_completed": len(session["rounds"]),
        "document_name": session["document_name"],
        "pending_gates": session["pending_gates"],
        "gate_records_count": len(session.get("gate_records", [])),
    }


@app.get("/api/sessions/{session_id}/results")
async def get_results(session_id: str):
    """Get full analysis results."""
    session = _get_session(session_id)
    engine: DebateEngineV3 = session["engine"]

    return {
        "session_id": session_id,
        "status": session["status"],
        "config": session["config"],
        "rounds": session["rounds"],
        "total_rounds": len(session["rounds"]),
        "cluster_summaries": {
            cid: summary.get("parsed", {})
            for cid, summary in engine.cluster_summaries.items()
        },
        "devil_advocate": engine.devil_advocate_output.get("parsed", {}) if engine.devil_advocate_output else None,
        "final_synthesis": engine.master_summaries[-1].get("parsed", {}) if engine.master_summaries else None,
        "gate_records": session.get("gate_records", []),
        "execution_metrics": session.get("execution_metrics", {}),
    }


@app.get("/api/sessions/{session_id}/gates")
async def get_gates(session_id: str):
    """Get pending and resolved gates."""
    session = _get_session(session_id)
    engine: DebateEngineV3 = session["engine"]

    return {
        "session_id": session_id,
        "pending_gates": [
            {
                "gate_number": g.gate_number,
                "gate_type": g.gate_type.value,
                "trigger_value": g.trigger_value,
                "threshold": g.threshold,
                "affected_cluster": g.affected_cluster,
                "description": g.description,
            }
            for g in engine.gate_evaluator.get_pending_gates()
        ] if hasattr(engine, 'gate_evaluator') else [],
        "all_gates": engine.get_all_gate_records() if hasattr(engine, 'get_all_gate_records') else [],
    }


@app.post("/api/sessions/{session_id}/gate-decision")
async def submit_gate_decision(session_id: str, request: GateDecisionRequest):
    """Submit human expert decision for a gate."""
    session = _get_session(session_id)
    engine: DebateEngineV3 = session["engine"]

    if request.gate_number not in session["pending_gates"]:
        raise HTTPException(
            status_code=400,
            detail=f"Gate {request.gate_number} is not pending"
        )

    result = engine.submit_gate_decision(
        gate_number=request.gate_number,
        decision=request.decision.value if hasattr(request.decision, 'value') else request.decision,
        reasoning=request.reasoning,
        human_review_id=request.human_review_id,
        override_score=request.override_score,
        override_classification=request.override_classification.value if request.override_classification else None,
    )

    if result is None:
        raise HTTPException(status_code=400, detail="Failed to resolve gate")

    # Remove from pending
    if request.gate_number in session["pending_gates"]:
        session["pending_gates"].remove(request.gate_number)

    # Add event
    session["events"].append({
        "type": "GATE_RESOLVED",
        "gate_number": request.gate_number,
        "decision": request.decision.value if hasattr(request.decision, 'value') else request.decision,
        "human_review_id": request.human_review_id,
        "timestamp": datetime.now().isoformat(),
    })

    # Update status if all gates resolved
    if not session["pending_gates"]:
        session["status"] = "awaiting_feedback"
        session["events"].append({
            "type": "ALL_GATES_RESOLVED",
            "timestamp": datetime.now().isoformat(),
        })

    return {
        "status": "gate_resolved",
        "gate_number": request.gate_number,
        "decision": request.decision.value if hasattr(request.decision, 'value') else request.decision,
        "remaining_pending": session["pending_gates"],
    }


@app.post("/api/sessions/{session_id}/feedback")
async def submit_feedback(session_id: str, request: FeedbackRequest):
    """Submit user feedback to trigger cluster re-analysis."""
    session = _get_session(session_id)

    if session["status"] not in ("awaiting_feedback", "running"):
        raise HTTPException(status_code=400, detail="Session is not awaiting feedback")

    session["status"] = "running"
    asyncio.create_task(_run_feedback_bg(session_id, request.feedback))

    return {
        "status": "feedback_received",
        "session_id": session_id,
        "message": "Feedback routed to appropriate cluster. Re-analysis in progress.",
    }


@app.post("/api/sessions/{session_id}/accept")
async def accept_result(session_id: str):
    """Mark the session as complete."""
    session = _get_session(session_id)
    session["status"] = "completed"
    return {"status": "completed", "session_id": session_id}
