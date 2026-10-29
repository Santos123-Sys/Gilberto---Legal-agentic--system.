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
from copy import deepcopy
from contextlib import closing
import json
import uuid
from functools import lru_cache
from time import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from hmac import compare_digest
from urllib.parse import urlparse

from config import settings
from financial.planning import estimate_plan
import session_store
from provider import ProviderError
from document_extractor import DocumentExtractionError, extract_document_text
from engines.debate_engine_v3 import DebateEngineV3, ReanalysisRequested, WorkflowError
from scoring import classification_for
from agents.cluster_definitions import CLUSTERS
from security.oidc import (Principal, AuthenticationRejected, IdentityNotConfigured,
                           build_jwks_resolver, verify_access_token)
from security.authorization import AccessDenied, require_session_owner
from security import local_identity
import backup_operations
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

@app.on_event("startup")
async def start_backup_scheduler():
    if settings.AUTH_MODE == "local":
        # The empty identity/checkpoint stores must exist before first backup.
        with closing(local_identity.connect()):
            pass
        with closing(session_store.connect()):
            pass
        if backup_operations.enabled():
            app.state.backup_task = asyncio.create_task(backup_operations.periodic_backup())


@app.on_event("shutdown")
async def stop_backup_scheduler():
    task = getattr(app.state, "backup_task", None)
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# ─────────────────────────────────────────────
#  IN-MEMORY SESSION STORE
# ─────────────────────────────────────────────

sessions: Dict[str, dict] = {}


@lru_cache(maxsize=8)
def _trusted_key_resolver(issuer: str, audience: str, jwks_url: str):
    return build_jwks_resolver(jwks_url, issuer=issuer, audience=audience)


def current_principal(request: Request) -> Principal:
    """Fail-closed bearer validation for every resource API, without query tokens."""
    if settings.AUTH_MODE == "local":
        entry = local_identity.resolve_session(request.cookies.get(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE)))
        if not entry:
            raise HTTPException(status_code=401, detail="Authentication required")
        return Principal(issuer=local_identity.LOCAL_ISSUER,
                         subject=entry["id"], expires_at=entry["expires_at"])
    if settings.AUTH_MODE != "oidc":
        raise HTTPException(status_code=503, detail="Authentication mode is invalid")
    issuer, audience, keys = settings.OIDC_ISSUER, settings.OIDC_AUDIENCE, settings.OIDC_JWKS_URL
    if not issuer or not audience or not keys:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        return verify_access_token(request.headers.get("Authorization"), issuer=issuer,
                                  audience=audience,
                                  signing_key_resolver=_trusted_key_resolver(issuer, audience, keys))
    except IdentityNotConfigured:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None
    except AuthenticationRejected:
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"}) from None



# Authentication routes use short-lived opaque cookie sessions and never
# store client credentials, access tokens or API keys in localStorage.
class LocalLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class LocalBootstrapRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    bootstrap_token: str = Field(min_length=32, max_length=512)


class LocalPasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def _local_only():
    if settings.AUTH_MODE != "local":
        raise HTTPException(status_code=404, detail="Not found")


def _issue_cookie(response: Response, token: str):
    response.set_cookie(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE), token, max_age=local_identity.SESSION_TTL,
                        secure=settings.LOCAL_AUTH_COOKIE_SECURE, httponly=True,
                        samesite="strict", path="/")


@app.get("/api/auth/bootstrap-status")
async def local_bootstrap_status():
    _local_only()
    enabled = (not local_identity.has_bootstrapped() and
               len(settings.LOCAL_BOOTSTRAP_TOKEN_SHA256) == 64 and
               settings.LOCAL_BOOTSTRAP_EXPIRES_AT > int(time()))
    return {"available": enabled}


@app.post("/api/auth/bootstrap")
async def local_bootstrap(body: LocalBootstrapRequest, response: Response):
    _local_only()
    if local_identity.has_bootstrapped():
        raise HTTPException(status_code=409, detail="Initial setup is already complete")
    try:
        token, user = local_identity.bootstrap_first_admin(
            body.email, body.password, body.bootstrap_token,
            token_hash=settings.LOCAL_BOOTSTRAP_TOKEN_SHA256,
            expires_at=settings.LOCAL_BOOTSTRAP_EXPIRES_AT)
    except (local_identity.LoginRejected, ValueError):
        raise HTTPException(status_code=403, detail="Initial setup is unavailable or invalid") from None
    _issue_cookie(response, token)
    return {"user": user, "status": "administrator_created"}


def _require_local_admin(principal: Principal):
    _local_only()
    if principal.issuer != local_identity.LOCAL_ISSUER or (
        local_identity.user_role(principal.subject) != "admin"
    ):
        raise HTTPException(status_code=403, detail="Administrator access required")


@app.get("/api/admin/backups/status")
async def backup_status(principal: Principal = Depends(current_principal)):
    _require_local_admin(principal)
    return {"enabled": backup_operations.enabled(), **backup_operations.get_status()}


@app.post("/api/admin/backups/run")
async def backup_run(principal: Principal = Depends(current_principal)):
    _require_local_admin(principal)
    try:
        return await backup_operations.run_backup()
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Backup is unavailable or running") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Backup failed; inspect restricted status") from None


@app.post("/api/admin/backups/verify")
async def backup_verify(principal: Principal = Depends(current_principal)):
    _require_local_admin(principal)
    try:
        return await backup_operations.verify_latest_offsite()
    except RuntimeError:
        raise HTTPException(status_code=409, detail="No backup is ready for verification") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Restore verification failed") from None


@app.get("/api/admin/users")
async def local_admin_users(principal: Principal = Depends(current_principal)):
    _local_only()
    if principal.issuer != local_identity.LOCAL_ISSUER:
        raise HTTPException(status_code=403, detail="Administrator access required")
    try:
        users = local_identity.list_users_for_admin(principal.subject)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Administrator access required") from None
    return {"users": users}


@app.post("/api/auth/login")
async def local_login(body: LocalLoginRequest, response: Response, request: Request):
    _local_only()
    try:
        token, user = local_identity.login(body.email, body.password,
                         request.client.host if request.client else "unknown")
    except local_identity.LoginRejected as exc:
        if exc.throttled:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.",
                                headers={"Retry-After": "900"}) from None
        raise HTTPException(status_code=401, detail="Invalid email or password") from None
    _issue_cookie(response, token)
    return {"user": user}


@app.get("/api/auth/me")
async def local_me(request: Request):
    _local_only()
    account = local_identity.resolve_session(request.cookies.get(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE)))
    if not account:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"user": {"id": account["id"], "email": account["email"], "role": account["role"]}}


@app.post("/api/auth/logout")
async def local_logout(request: Request, response: Response):
    _local_only()
    local_identity.revoke_session(request.cookies.get(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE)))
    response.delete_cookie(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE), path="/",
                           secure=settings.LOCAL_AUTH_COOKIE_SECURE, httponly=True,
                           samesite="strict")
    return {"status": "signed_out"}


@app.post("/api/auth/change-password")
async def local_change_password(body: LocalPasswordChangeRequest,
                                request: Request, response: Response):
    _local_only()
    entry = local_identity.resolve_session(request.cookies.get(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE)))
    if not entry:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        token = local_identity.change_password(entry["id"], body.current_password,
                                               body.new_password)
    except local_identity.PasswordRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _issue_cookie(response, token)
    return {"status": "password_changed"}


def _get_session(session_id: str, principal: Principal) -> dict:
    if session_id not in sessions:
        try:
            recovered = session_store.load(session_id, DebateEngineV3)
        except session_store.SessionCheckpointError as exc:
            # Preserve the damaged record for forensic recovery; never expose raw
            # checkpoint content, storage paths or internal traces to the client.
            raise HTTPException(status_code=503, detail="Saved review checkpoint is unavailable.") from exc
        if recovered is not None:
            sessions[session_id] = recovered
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        require_session_owner(principal, sessions[session_id])
    except AccessDenied:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return sessions[session_id]


@app.middleware("http")
async def checkpoint_mutations(request: Request, call_next):
    if settings.AUTH_MODE == "local" and request.url.path.startswith("/api/") and request.url.path not in ("/api/health", "/api/ready"):
        secret = settings.LOCAL_AUTH_PROXY_SECRET
        origin = settings.LOCAL_AUTH_APP_ORIGIN
        if not secret or len(secret) < 32 or not origin:
            return JSONResponse(status_code=503, content={"detail": "Local authentication is not configured"})
        if not settings.LOCAL_AUTH_COOKIE_SECURE and not (
            origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")
        ):
            return JSONResponse(status_code=503, content={"detail": "Secure cookies are required"})
        supplied = request.headers.get("X-Gilberto-Proxy-Auth", "")
        if not compare_digest(supplied, secret):
            return JSONResponse(status_code=403, content={"detail": "Proxy access denied"})
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("Origin") != origin:
                return JSONResponse(status_code=403, content={"detail": "Untrusted request origin"})
    response = await call_next(request)
    if request.url.path.startswith(("/api/sessions", "/api/auth")):
        # Legal documents and derived results must not be cached by browsers or proxies.
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
    if request.method == "POST" and response.status_code < 300:
        # Save only the session addressed by this mutation. Background analysis
        # checkpoints its own events; POST /api/sessions saves explicitly.
        segments = request.url.path.strip("/").split("/")
        if len(segments) == 4 and segments[:2] == ["api", "sessions"]:
            session = sessions.get(segments[2])
            if session is not None:
                session_store.save(session)
    return response


# ─────────────────────────────────────────────
#  BACKGROUND TASK RUNNERS
# ─────────────────────────────────────────────

def _append_event(session, event):
    session["events"].append({**deepcopy(event), "event_id": len(session["events"]) + 1,
                              "session_id": session["id"]})


async def _run_analysis_bg(session_id: str, document_text: str, feedback=None):
    """One accountable task per session; re-analysis reuses the same task and budget."""
    session = sessions[session_id]
    engine = session["engine"]
    try:
        while True:
            stream = (engine.run_debate(document_text) if feedback is None else
                      engine.process_feedback(feedback, document_text))
            try:
                async for event in stream:
                    _append_event(session, event)
                    kind = event["type"]
                    if kind == "ROUND_COMPLETE":
                        session["rounds"].append({
                            "round": event.get("round"), "summary": deepcopy(event.get("summary", {})),
                            "gates_triggered": event.get("gates_triggered", []),
                            "latency_ms": event.get("latency_ms", 0),
                        })
                    elif kind == "GATE_TRIGGERED":
                        session["pending_gates"].append(event["gate_id"])
                        session["status"] = "awaiting_gate"
                    elif kind == "ALL_GATES_RESOLVED":
                        session["pending_gates"] = []
                        session["status"] = "running"
                    elif kind == "DEBATE_COMPLETE":
                        session["status"] = "awaiting_feedback"
                        session["execution_metrics"] = engine.get_metrics()
                        session["gate_records"] = engine.get_all_gate_records()
                    elif kind == "ERROR":
                        raise RuntimeError(event.get("message", "Analysis failed"))
                    session_store.save(session)
                break
            except ReanalysisRequested as exc:
                if session["feedback_rounds"] >= settings.MAX_FEEDBACK_ROUNDS:
                    raise WorkflowError("Re-analysis limit reached; retained findings require manual review") from exc
                session["feedback_rounds"] += 1
                session["status"] = "running"
                feedback = str(exc)
    except asyncio.CancelledError:
        session["status"] = "cancelled"
        session["error"] = None
        session.get("cancellation", {}).update(state="confirmed")
        _append_event(session, {"type": "CANCELLED",
                                "message": "Orchestration stopped. An in-flight provider call may still finish.",
                                "timestamp": datetime.now().isoformat()})
        raise
    except Exception as exc:
        # Do not expose provider payloads or contract excerpts in operational errors.
        session["status"] = "error"
        session["error"] = (str(exc) if isinstance(exc, (WorkflowError, ProviderError)) else
            "Analysis could not finish because a provider call or output validation failed. Completed findings are retained for manual review.")
        _append_event(session, {"type": "ERROR", "message": session["error"],
                                "error_type": type(exc).__name__,
                                "timestamp": datetime.now().isoformat()})
    finally:
        engine._running = False
        session["execution_metrics"] = engine.get_metrics()
        session["gate_records"] = engine.get_all_gate_records()
        session_store.save(session)


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "session_storage": "sqlite_checkpoint",
        "provider": {"name": "Maritaca", "model": settings.MARITACA_MODEL,
                     "configured": bool(settings.MARITACA_API_KEY.strip()), "transport": "direct_chat_completion"},
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


@app.get("/api/ready")
async def ready():
    # Liveness and readiness differ: don't route users to an instance that
    # cannot read their persisted legal review checkpoints.
    try:
        session_store.is_ready()
    except Exception:
        raise HTTPException(status_code=503, detail="Session storage is unavailable")
    return {"status": "ready"}


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest, principal: Principal = Depends(current_principal)):
    """Create a new debate session with specified configuration."""
    if request.num_rounds > settings.MAX_ROUNDS:
        raise HTTPException(status_code=422, detail="Requested rounds exceed the configured limit")
    if request.jurisdiction != "BR":
        raise HTTPException(status_code=422, detail="Only Brazilian jurisdiction is supported")
    session_id = str(uuid.uuid4())
    engine = DebateEngineV3(
        session_id=session_id,
        num_agents=request.num_agents,
        num_rounds=request.num_rounds,
        workflow_type=request.workflow_type.value if hasattr(request.workflow_type, 'value') else str(request.workflow_type),
    )

    engine.review_depth = request.review_depth
    config = request.model_dump(exclude={'user_id'})
    active = [cid for cid in engine.feedback_agents if cid in settings.active_clusters_list]
    config["active_clusters"] = [{"id": cid, "name": CLUSTERS[cid]["name"],
                                  "agents": 1 if request.review_depth == "focused" else len(CLUSTERS[cid]["agents"])} for cid in active]
    config["num_agents"] = sum(item["agents"] for item in config["active_clusters"])
    config["initial_model_calls"] = sum((2 * c["agents"] + 1) if c["agents"] > 1 else 2 for c in config["active_clusters"]) * request.num_rounds + 2 * request.num_rounds
    config["max_feedback_rounds"] = settings.MAX_FEEDBACK_ROUNDS
    config["model_call_budget"] = settings.MAX_MODEL_CALLS
    config["cost_preflight"] = estimate_plan(
        config["initial_model_calls"], settings.MAX_TOKENS,
        input_usd_per_million=settings.LLM_INPUT_PRICE_USD_PER_1M,
        output_usd_per_million=settings.LLM_OUTPUT_PRICE_USD_PER_1M,
        hard_cap_usd=settings.MAX_REVIEW_ESTIMATED_USD,
    )
    if not active:
        raise HTTPException(status_code=503, detail="No specialist workstreams are configured")

    sessions[session_id] = {
        "id": session_id,
        "owner_issuer": principal.issuer,
        "owner_subject": principal.subject,
        "engine": engine,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "config": config,
        "rounds": [],
        "events": [],
        "pending_gates": [],
        "gate_records": [],
        "execution_metrics": {},
        "document_text": None,
        "document_name": None,
        "error": None,
        "task": None,
        "feedback_rounds": 0,
    }

    # Persist the new session even when created outside the HTTP middleware.
    session_store.save(sessions[session_id])
    return SessionResponse(
        session_id=session_id,
        status="created",
        config=config,
    )


@app.post("/api/sessions/{session_id}/start")
async def start_session(session_id: str, document: UploadFile = File(...),
                        principal: Principal = Depends(current_principal)):
    """Upload the legal document and start the debate."""
    session = _get_session(session_id, principal)

    if session["status"] != "created":
        raise HTTPException(status_code=400, detail="Session already started")

    content = await document.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB upload limit")

    try:
        document_text = extract_document_text(document.filename or "", content)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Reading the upload yields; check again before committing the start.
    if session["status"] != "created":
        raise HTTPException(status_code=409, detail="Session already started")
    # Fail before paid-model dispatch when the single-worker execution pool is full.
    # Gate-paused analyses still occupy resources and are counted.
    active = sum(
        item["status"] in ("running", "awaiting_gate")
        for item in sessions.values()
    )
    if active >= settings.MAX_CONCURRENT_ANALYSES:
        raise HTTPException(
            status_code=429,
            detail="Analysis capacity is full. Try again after an active review finishes.",
        )
    session["document_text"] = document_text
    session["document_name"] = document.filename
    session["status"] = "running"

    session["task"] = asyncio.create_task(_run_analysis_bg(session_id, document_text))

    return {
        "status": "started",
        "session_id": session_id,
        "filename": document.filename,
        "document_format": (document.filename or "").rsplit(".", 1)[-1].lower(),
        "extracted_characters": len(document_text),
        "architecture": "parallel_v3",
    }


@app.get("/api/sessions/{session_id}/stream")
async def stream_events(session_id: str, request: Request, cursor: int = Query(default=0, ge=0),
                        principal: Principal = Depends(current_principal)):
    """Server-Sent Events stream with cursor-based resume."""
    session = _get_session(session_id, principal)
    if cursor > len(session["events"]):
        raise HTTPException(status_code=409, detail="Event cursor exceeds session history")

    async def generator():
        session = sessions[session_id]
        idx = cursor

        heartbeat_at = asyncio.get_running_loop().time()
        while not await request.is_disconnected():
            if principal.expires_at is not None and time() >= principal.expires_at:
                break
            if settings.AUTH_MODE == "local":
                active = local_identity.resolve_session(request.cookies.get(local_identity.cookie_name(settings.LOCAL_AUTH_COOKIE_SECURE)))
                if not active or active["id"] != principal.subject:
                    break
            events = session["events"]

            while idx < len(events):
                yield f"id: {idx + 1}\ndata: {json.dumps(events[idx])}\n\n"
                idx += 1

            if session["status"] in ("completed", "error", "cancelled"):
                yield f"data: {json.dumps({'type': 'STREAM_END', 'timestamp': datetime.now().isoformat()})}\n\n"
                break

            if asyncio.get_running_loop().time() - heartbeat_at >= 15:
                yield ": heartbeat\n\n"
                heartbeat_at = asyncio.get_running_loop().time()
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
async def get_status(session_id: str, principal: Principal = Depends(current_principal)):
    """Get current session status."""
    session = _get_session(session_id, principal)
    return {
        "session_id": session_id,
        "status": session["status"],
        "current_round": session["engine"].current_round,
        "total_rounds": session["config"]["num_rounds"],
        "events_count": len(session["events"]),
        "rounds_completed": len(session["rounds"]),
        "document_name": session["document_name"],
        "pending_gates": session["pending_gates"],
        "gate_records_count": len(session["engine"].get_all_gate_records()),
        "feedback_rounds": session["feedback_rounds"],
        "error": session["error"],
    }


@app.get("/api/sessions/{session_id}/results")
async def get_results(session_id: str, principal: Principal = Depends(current_principal)):
    """Get full analysis results."""
    session = _get_session(session_id, principal)
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
        "gate_records": engine.get_all_gate_records(),
        "execution_metrics": engine.get_metrics(),
        "partial": session["status"] == "error",
    }


@app.get("/api/sessions/{session_id}/gates")
async def get_gates(session_id: str, principal: Principal = Depends(current_principal)):
    """Get pending and resolved gates."""
    session = _get_session(session_id, principal)
    engine: DebateEngineV3 = session["engine"]

    return {
        "session_id": session_id,
        "pending_gates": engine.get_pending_gates(),
        "all_gates": engine.get_all_gate_records() if hasattr(engine, 'get_all_gate_records') else [],
    }


@app.post("/api/sessions/{session_id}/gate-decision")
async def submit_gate_decision(session_id: str, request: GateDecisionRequest, principal: Principal = Depends(current_principal)):
    """Submit human expert decision for a gate."""
    session = _get_session(session_id, principal)
    engine: DebateEngineV3 = session["engine"]

    if request.session_id != session_id:
        raise HTTPException(status_code=409, detail="Decision belongs to another session")
    if session["status"] != "awaiting_gate":
        raise HTTPException(status_code=409, detail="Session is not awaiting review")
    matches = [g for g in engine.get_pending_gates() if g["gate_number"] == request.gate_number
               and (request.gate_id is None or g["gate_id"] == request.gate_id)]
    if len(matches) != 1:
        raise HTTPException(status_code=409, detail="Review is stale or ambiguous; refresh the pending reviews")
    if not request.reasoning.strip():
        raise HTTPException(status_code=422, detail="Review reasoning is required")
    if request.decision.value == "request_reanalysis" and session["feedback_rounds"] >= settings.MAX_FEEDBACK_ROUNDS:
        raise HTTPException(status_code=409, detail="Re-analysis limit reached; review manually or start a new analysis")
    if request.decision.value == "override" and request.override_score is None:
        raise HTTPException(status_code=422, detail="An override score is required")
    if request.override_classification and request.override_score is not None:
        if request.override_classification.value != classification_for(request.override_score):
            raise HTTPException(status_code=422, detail="Override classification does not match its score")
    gate_id = matches[0]["gate_id"]
    result = engine.submit_gate_decision(
        gate_number=request.gate_number, gate_id=gate_id,
        decision=request.decision.value, reasoning=request.reasoning,
        human_review_id=principal.subject, override_score=request.override_score,
        override_classification=request.override_classification.value if request.override_classification else None,
    )
    if result is None:
        raise HTTPException(status_code=409, detail="Review already resolved")
    # Keep the model result intact and record the expert adjustment separately.
    if request.decision.value == "override" and engine.master_summaries:
        synthesis = engine.master_summaries[-1]["parsed"]
        synthesis.setdefault("model_assessment", {
            key: synthesis[key] for key in ("final_score", "final_classification")
        })
        synthesis.update(final_score=request.override_score,
                         final_classification=classification_for(request.override_score),
                         human_override={"gate_id": gate_id, "reasoning": request.reasoning,
                                         "reviewer": principal.subject})
    if (request.decision.value == "override" and request.override_score >= 8
            and settings.GATE_3_ALWAYS_FOR_CRITICO
            and not any(g["gate_number"] == 3 and g.get("round") == engine.current_round
                        for g in engine.get_all_gate_records())):
        trigger = {"gate_number": 3, "trigger_type": "critico_classification",
                   "trigger_value": request.override_score, "threshold": 8.0,
                   "affected_cluster": None,
                   "description": "The expert override raises the final classification to Crítico; senior review is required"}
        gate = engine.gate_evaluator.record_trigger(trigger)
        gate["round"] = engine.current_round
        _append_event(session, {"type": "GATE_TRIGGERED", "gate_id": gate["gate_id"],
                                "gate_number": 3, "trigger": trigger, "record": gate,
                                "timestamp": datetime.now().isoformat()})
    session["pending_gates"] = [g["gate_id"] for g in engine.get_pending_gates()]
    session["gate_records"] = engine.get_all_gate_records()
    _append_event(session, {"type": "GATE_RESOLVED", "gate_number": request.gate_number,
                            "gate_id": gate_id, "record": result,
                            "summary": engine.master_summaries[-1]["parsed"] if engine.master_summaries else None,
                            "decision": request.decision.value, "timestamp": datetime.now().isoformat()})
    if not session["pending_gates"]:
        session["status"] = "running"  # The engine must finish/continue before acceptance.
        _append_event(session, {"type": "ALL_GATES_RESOLVED", "timestamp": datetime.now().isoformat()})
    return {"status": session["status"], "gate_id": gate_id, "record": result,
            "remaining_pending": session["pending_gates"]}


@app.post("/api/sessions/{session_id}/feedback")
async def submit_feedback(session_id: str, request: FeedbackRequest, principal: Principal = Depends(current_principal)):
    """Submit user feedback to trigger cluster re-analysis."""
    session = _get_session(session_id, principal)

    if session["status"] != "awaiting_feedback" or (session["task"] and not session["task"].done()):
        raise HTTPException(status_code=400, detail="Session is not awaiting feedback")

    if session["feedback_rounds"] >= settings.MAX_FEEDBACK_ROUNDS:
        raise HTTPException(status_code=409, detail="Re-analysis limit reached")
    session["feedback_rounds"] += 1
    session["status"] = "running"
    session["error"] = None
    session["task"] = asyncio.create_task(_run_analysis_bg(session_id, session["document_text"], request.feedback))

    return {
        "status": "feedback_received",
        "session_id": session_id,
        "message": "Feedback routed to appropriate cluster. Re-analysis in progress.",
    }


def _finish_cancel(session):
    if session["status"] != "cancellation_requested":
        return
    session["status"] = "cancelled"
    session["error"] = None
    session.get("cancellation", {}).update(state="confirmed")
    _append_event(session, {"type": "CANCELLED",
                            "message": "Orchestration stopped. An in-flight provider call may still finish.",
                            "timestamp": datetime.now().isoformat()})
    session_store.save(session)


@app.post("/api/sessions/{session_id}/cancel")
async def cancel_session(session_id: str, principal: Principal = Depends(current_principal)):
    """Stop new dispatch. Cannot undo or forcibly terminate an in-flight thread."""
    session = _get_session(session_id, principal)
    if session["status"] in ("cancelled", "cancellation_requested"):
        return {"status": session["status"], "provider_in_flight_possible": True}
    if session["status"] not in ("created", "running", "awaiting_gate"):
        raise HTTPException(status_code=409, detail="This review cannot be cancelled in its current state")
    session["engine"]._provider_aborted = True
    session["status"] = "cancellation_requested"
    session["cancellation"] = {
        "requested_by_issuer": principal.issuer,
        "requested_by_subject": principal.subject,
        "requested_at": datetime.now().isoformat(),
        "state": "requested",
    }
    _append_event(session, {"type": "CANCEL_REQUESTED",
                            "message": "Stopping new model and tool dispatch",
                            "timestamp": datetime.now().isoformat()})
    session_store.save(session)
    task = session.get("task")
    if task and not task.done():
        task.add_done_callback(lambda _: _finish_cancel(session))
        task.cancel()
    else:
        _finish_cancel(session)
    return {"status": session["status"], "provider_in_flight_possible": True}


@app.post("/api/sessions/{session_id}/accept")
async def accept_result(session_id: str, principal: Principal = Depends(current_principal)):
    """Mark the session as complete."""
    session = _get_session(session_id, principal)
    if session["status"] == "completed":
        return {"status": "completed", "session_id": session_id}
    if (session["status"] != "awaiting_feedback" or session["pending_gates"]
            or session["engine"].gate_evaluator.has_pending_gates()
            or not session["engine"].master_summaries
            or (session["task"] and not session["task"].done())):
        raise HTTPException(status_code=409, detail="Finish the analysis and all required reviews before acceptance")
    session["status"] = "completed"
    return {"status": "completed", "session_id": session_id}

