"""Privacy-preserving review-level reliability metrics.

Only summarize passed records already present in memory. This is NOT a claim
of availability, historical persistence, RTO/RPO, incident-free operation or
production service-level compliance.
"""
from collections import Counter
from math import ceil

STATES = ("created", "running", "awaiting_gate", "awaiting_feedback",
          "completed", "error", "cancelled")


def _percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[max(0,ceil(p * len(values))-1)],2)


def summarize_sessions(records):
    statuses = Counter()
    durations=[]
    calls=0
    failures=0
    for session in records:
        state = str(session.get("status", "unknown")).lower()
        statuses[state if state in STATES else "unknown"] += 1
        metrics=session.get("execution_metrics") or {}
        if not isinstance(metrics,dict):
            metrics={}
        latency=metrics.get("total_latency_ms")
        if isinstance(latency,(float,int)) and not isinstance(latency,bool) and 0 <= latency <= 10**10:
            durations.append(float(latency))
        count=metrics.get("model_calls")
        if isinstance(count,int) and not isinstance(count,bool) and count>=0:
            calls+=count
        if state == "error":
            failures+=1
    return {
        "basis":"in_memory_session_snapshot_only",
        "history_complete":False,
        "availability_measured":False,
        "legal_accuracy_measured":False,
        "sample_size":sum(statuses.values()),
        "states":dict(statuses),
        "failed_sessions":failures,
        "model_calls_reported":calls,
        "completed_duration_sample_size":len(durations),
        "p50_latency_ms":_percentile(durations,.50),
        "p95_latency_ms":_percentile(durations,.95),
        "sensitive_data_included":False,
    }
