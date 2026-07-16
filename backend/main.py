"""
Gilberto Legal Agent — FastAPI Backend
────────────────────────────────────────
Endpoints:
  POST   /api/sessions                      Create session
  POST   /api/sessions/{id}/start           Upload doc + start debate
  GET    /api/sessions/{id}/stream          SSE stream of debate events
  GET    /api/sessions/{id}/status          Current session status
  GET    /api/sessions/{id}/results         Full results after debate
  POST   /api/sessions/{id}/feedback        Submit user feedback
  POST   /api/sessions/{id}/accept          Mark session as complete
  GET    /api/health                        Health check
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings
from debate_engine import DebateEngine
from models.schemas import (
    FeedbackRequest,
    SessionCreateRequest,
    SessionResponse,
)

# ─────────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Gilberto Legal Agent API",
    description="Multi-agent AI debate system for legal document analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
#  IN-MEMORY SESSION STORE
#  Replace with Redis or PostgreSQL for
#  multi-instance / persistent deployments
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
    session = sessions[session_id]
    engine: DebateEngine = session["engine"]
    try:
        async for event in engine.run_debate(document_text):
            session["events"].append(event)
            if event["type"] == "ROUND_COMPLETE":
                session["rounds"].append(event.get("round_data", {}))
            elif event["type"] == "DEBATE_COMPLETE":
                session["status"] = "awaiting_feedback"
            elif event["type"] == "ERROR":
                session["status"] = "error"
    except Exception as exc:
        session["events"].append(
            {"type": "ERROR", "message": str(exc), "timestamp": datetime.now().isoformat()}
        )
        session["status"] = "error"


async def _run_feedback_bg(session_id: str, feedback: str):
    session = sessions[session_id]
    engine: DebateEngine = session["engine"]
    document_text: str = session.get("document_text", "")
    try:
        async for event in engine.process_feedback(feedback, document_text):
            session["events"].append(event)
            if event["type"] == "ROUND_COMPLETE":
                session["rounds"].append(event.get("round_data", {}))
            elif event["type"] == "DEBATE_COMPLETE":
                session["status"] = "awaiting_feedback"
    except Exception as exc:
        session["events"].append(
            {"type": "ERROR", "message": str(exc), "timestamp": datetime.now().isoformat()}
        )
        session["status"] = "error"


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new debate session with specified configuration."""
    session_id = str(uuid.uuid4())
    engine = DebateEngine(
        session_id=session_id,
        num_agents=request.num_agents,
        num_rounds=request.num_rounds,
        workflow_type=request.workflow_type,
    )
    sessions[session_id] = {
        "id": session_id,
        "engine": engine,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "config": request.model_dump(),
        "rounds": [],
        "events": [],
        "document_text": None,
        "document_name": None,
    }
    return SessionResponse(
        session_id=session_id,
        status="created",
        config=request.model_dump(),
    )


@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str, document: UploadFile = File(...)):
    """
    Upload the legal document and start the debate.
    Accepts: .txt, .pdf (text-only), or plain text content.
    """
    session = _get_session(session_id)

    if session["status"] != "created":
        raise HTTPException(status_code=400, detail="Session already started")

    content = await document.read()

    # Attempt UTF-8 decode (works for .txt; for real PDFs use pdfplumber)
    try:
        document_text = content.decode("utf-8")
    except UnicodeDecodeError:
        document_text = content.decode("latin-1", errors="replace")

    if len(document_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Document appears to be empty or too short")

    session["document_text"] = document_text
    session["document_name"] = document.filename
    session["status"] = "running"

    # Fire debate in the background
    asyncio.create_task(_run_debate_bg(session_id, document_text))

    return {"status": "started", "session_id": session_id, "filename": document.filename}


@app.get("/api/sessions/{session_id}/stream")
async def stream_events(session_id: str, cursor: int = 0):
    """
    Server-Sent Events stream.
    The client passes `cursor` (index of last received event) to resume.
    """
    _get_session(session_id)  # Validate existence

    async def generator():
        session = sessions[session_id]
        idx = cursor

        while True:
            events = session["events"]

            # Send any new events
            while idx < len(events):
                yield f"data: {json.dumps(events[idx])}\n\n"
                idx += 1

            # Terminal state — close the stream
            if session["status"] in ("completed", "error"):
                yield f"data: {json.dumps({'type': 'STREAM_END', 'timestamp': datetime.now().isoformat()})}\n\n"
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/sessions/{session_id}/status")
async def get_status(session_id: str):
    session = _get_session(session_id)
    return {
        "session_id": session_id,
        "status": session["status"],
        "current_round": session["engine"].current_round,
        "total_rounds": session["config"]["num_rounds"],
        "num_agents": session["config"]["num_agents"],
        "events_count": len(session["events"]),
        "rounds_completed": len(session["rounds"]),
        "document_name": session["document_name"],
    }


@app.get("/api/sessions/{session_id}/results")
async def get_results(session_id: str):
    session = _get_session(session_id)
    return {
        "session_id": session_id,
        "status": session["status"],
        "config": session["config"],
        "rounds": session["rounds"],
        "total_rounds": len(session["rounds"]),
    }


@app.post("/api/sessions/{session_id}/feedback")
async def submit_feedback(session_id: str, request: FeedbackRequest):
    """Submit user feedback to trigger a new debate round with a Feedback Advocate agent."""
    session = _get_session(session_id)

    if session["status"] not in ("awaiting_feedback", "running"):
        raise HTTPException(status_code=400, detail="Session is not awaiting feedback")

    session["status"] = "running"
    asyncio.create_task(_run_feedback_bg(session_id, request.feedback))

    return {
        "status": "feedback_received",
        "session_id": session_id,
        "message": "A new Feedback Advocate agent has been created and a new debate round has started.",
    }


@app.post("/api/sessions/{session_id}/accept")
async def accept_result(session_id: str):
    """Mark the session as complete (user accepts the analysis)."""
    session = _get_session(session_id)
    session["status"] = "completed"
    return {"status": "completed", "session_id": session_id}
