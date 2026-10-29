"""Atomic SQLite checkpoints on a persistent volume; one API worker required."""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

class SessionCheckpointError(RuntimeError):
    """The saved session exists but cannot be safely reconstructed."""


ENGINE_FIELDS = ('current_round', 'cluster_summaries', 'devil_advocate_output',
                 'master_summaries', 'feedback_agents', 'execution_metrics',
                 '_legal_evidence_audits')


def connect():
    path = os.environ.get('SESSION_DB_PATH', 'data/sessions.sqlite3')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return connection


def is_ready() -> bool:
    """Report readiness only when the checkpoint database is accessible."""
    from contextlib import closing
    with closing(connect()) as db:
        db.execute('SELECT id FROM sessions LIMIT 1').fetchone()
    return True


def save(session):
    engine = session['engine']
    payload = {key: value for key, value in session.items() if key not in ('engine', 'task')}
    payload['engine_state'] = {key: getattr(engine, key) for key in ENGINE_FIELDS}
    payload['engine_state']['gate_records'] = engine.get_all_gate_records()
    # sqlite3.Connection's context manager commits, but does not close the connection.
    # Explicitly close after every checkpoint to avoid descriptor and WAL-lock leaks.
    with closing(connect()) as db:
        with db:
            db.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?)',
                       (session['id'], json.dumps(payload, ensure_ascii=False)))


def load(session_id, engine_factory):
    with closing(connect()) as db:
        row = db.execute('SELECT payload FROM sessions WHERE id = ?', (session_id,)).fetchone()
    if row is None:
        return None
    try:
        session = json.loads(row[0])
        state = session.pop('engine_state')
        config = session['config']
        engine = engine_factory(session_id, config['num_agents'], config['num_rounds'],
                                config['workflow_type'], provider_mode=config.get("provider_mode", "primary"))
        engine.review_depth = config.get("review_depth", "full")
        for key in ENGINE_FIELDS:
            if key == '_legal_evidence_audits':
                # Older checkpoints predate the legal audit and must stay
                # readable without inventing retrospectively reviewed claims.
                evidence = state.get(key, [])
                if not isinstance(evidence, list):
                    raise ValueError("Invalid persisted legal audit")
                setattr(engine, key, evidence)
            else:
                setattr(engine, key, state[key])
        engine.gate_evaluator.gate_records = state['gate_records']
        engine.gate_evaluator.pending_gates = [g for g in state['gate_records'] if g['status'] == 'pending']
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SessionCheckpointError("Stored checkpoint cannot be reconstructed") from exc
    session.update(engine=engine, task=None)
    if session['status'] in ('running', 'awaiting_gate', 'cancellation_requested'):
        session['status'] = 'error'
        session['error'] = 'Execution was interrupted by a server restart. Saved findings and review records are retained. Start a new analysis to continue safely.'
        session['events'].append({'type': 'ERROR', 'message': session['error'],
                                  'event_id': len(session['events']) + 1, 'session_id': session_id})
        save(session)
    return session
