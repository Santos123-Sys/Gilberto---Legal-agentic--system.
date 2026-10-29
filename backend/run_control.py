"""Server-owned execution projection, separate from legal-review workflow status.

The API runs one worker. Control handlers do not yield between the version check,
barrier mutation and checkpoint. SQLite is the durable checkpoint authority; this
is not a distributed lock and multiple API workers remain unsupported.
"""


def execution_state(session):
    status = session["status"]
    if status == "error":
        return "INTERRUPTED" if session.get("interrupted") else "ERROR"
    if status == "cancellation_requested":
        return "STOPPING" if session.get("cancellation", {}).get("state") == "stopping" else "STOP_REQUESTED"
    fixed = {"created": "CREATED", "cancelled": "STOPPED", "completed": "COMPLETED",
             "awaiting_gate": "AWAITING_HUMAN_REVIEW", "awaiting_feedback": "AWAITING_FEEDBACK"}
    if status in fixed:
        return fixed[status]
    control = session.get("run_control", "running")
    if control == "preparing":
        return "PREPARING"
    if control == "resuming":
        return "RESUMING"
    if control == "pause_requested":
        return "PAUSED" if session.get("pause_acknowledged") else "PAUSE_REQUESTED"
    return "RUNNING"


def synchronize(session):
    state = execution_state(session)
    if session.get("execution_state") != state:
        session["execution_state"] = state
        session["control_version"] = session.get("control_version", 0) + 1
    else:
        session.setdefault("control_version", 0)
    return {"execution_state": state, "control_version": session["control_version"]}


def response(session):
    return {**synchronize(session), "run_control": session.get("run_control", "running"),
            "provider_in_flight_possible": bool(getattr(session["engine"], "_active_provider_calls", 0))
                or session["status"] in ("cancellation_requested", "cancelled"),
            "resume_supported": session["status"] == "running" and
                session.get("run_control") == "pause_requested" and
                not session["engine"]._provider_aborted and not session["engine"]._provider_failure}
