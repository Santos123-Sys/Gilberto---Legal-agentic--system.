import os
import tempfile
import unittest
from unittest.mock import patch
from engines.debate_engine_v3 import DebateEngineV3
import session_store

class PersistenceTests(unittest.TestCase):
    def test_completed_and_interrupted_sessions_survive_new_engine(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/sessions.db'):
            for status in ('completed', 'running', 'awaiting_feedback', 'awaiting_gate'):
                engine = DebateEngineV3('synthetic',20,1,'general')
                engine.master_summaries = [{'parsed': {'executive_summary': 'retained result'}}]
                session = dict(id='synthetic', engine=engine, task=None, config=dict(num_agents=20,num_rounds=1,workflow_type='general'), status=status, events=[], error=None)
                session_store.save(session)
                restored = session_store.load('synthetic', DebateEngineV3)
                self.assertEqual(restored['engine'].master_summaries, engine.master_summaries)
                self.assertEqual(restored['status'], 'error' if status in ('running','awaiting_gate') else status)
                self.assertIsNone(restored['task'])
            self.assertIsNone(session_store.load('missing', DebateEngineV3))

    def test_corrupt_checkpoint_is_retained_and_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/sessions.db'):
            with session_store.connect() as db:
                db.execute('INSERT INTO sessions VALUES (?, ?)', ('broken', '{invalid JSON'))
            with self.assertRaises(session_store.SessionCheckpointError):
                session_store.load('broken', DebateEngineV3)
            with session_store.connect() as db:
                stored = db.execute('SELECT payload FROM sessions WHERE id = ?', ('broken',)).fetchone()
            self.assertEqual(stored[0], '{invalid JSON')
