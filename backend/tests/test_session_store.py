import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
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

    def test_backup_transfer_consent_restored_from_checkpoint_without_implicit_grant(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/sessions.db'):
            for expected in (True, False):
                engine = DebateEngineV3('backup-consent',20,1,'general',
                                        provider_mode='backup', backup_consent=expected)
                session = dict(id='backup-consent',engine=engine,task=None,
                               config=dict(num_agents=20,num_rounds=1,workflow_type='general',
                                           provider_mode='backup',backup_consent=expected),
                               status='awaiting_feedback',events=[],error=None)
                session_store.save(session)
                recovered=session_store.load('backup-consent',DebateEngineV3)
                self.assertIs(recovered['engine'].backup_consent, expected)
            # A legacy checkpoint with no explicit consent must never gain it.
            session['config'].pop('backup_consent')
            session_store.save(session)
            self.assertFalse(session_store.load('backup-consent',DebateEngineV3)['engine'].backup_consent)

    def test_checkpoint_and_load_close_sqlite_connections(self):
        import sqlite3
        raw_connect = sqlite3.connect
        connections = []
        def tracked_connect(*args, **kwargs):
            db = raw_connect(*args, **kwargs)
            connections.append(db)
            return db
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/audit.sqlite3'), patch.object(session_store.sqlite3, 'connect', side_effect=tracked_connect):
            engine = DebateEngineV3('tracked',20,1,'general')
            session = dict(id='tracked', engine=engine, task=None, config=dict(num_agents=20,num_rounds=1,workflow_type='general'), status='completed', events=[], error=None)
            session_store.save(session)
            restored = session_store.load('tracked', DebateEngineV3)
            self.assertEqual(restored['id'], 'tracked')
            self.assertEqual(len(connections), 2)
            for db in connections:
                with self.assertRaises(sqlite3.ProgrammingError):
                    db.execute('SELECT 1')

    def test_corrupt_checkpoint_is_retained_and_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/sessions.db'):
            with session_store.connect() as db:
                db.execute('INSERT INTO sessions VALUES (?, ?)', ('broken', '{invalid JSON'))
            with self.assertRaises(session_store.SessionCheckpointError):
                session_store.load('broken', DebateEngineV3)
            with session_store.connect() as db:
                stored = db.execute('SELECT payload FROM sessions WHERE id = ?', ('broken',)).fetchone()
            self.assertEqual(stored[0], '{invalid JSON')


class BrazilianEvidenceCheckpointTests(unittest.TestCase):
    def _session(self, engine, sid):
        return dict(id=sid, engine=engine, task=None,
                    config=dict(num_agents=20,num_rounds=1,workflow_type='general'),
                    status='awaiting_feedback', events=[], error=None)

    def test_roundtrip_preserves_unverified_agent_evidence_for_later_feedback(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/session.db'):
            engine=DebateEngineV3('case-evidence',20,1,'general')
            engine._legal_evidence_audits=[{
                'jurisdiction':'BR','review_required':True,'source_verification_status':'NOT_VERIFIED',
                'findings':[{'index':0,'status':'unsupported_or_unlocated_claim'}]
            }]
            session_store.save(self._session(engine,'case-evidence'))
            restored=session_store.load('case-evidence', DebateEngineV3)
            self.assertEqual(restored['engine']._legal_evidence_audits,engine._legal_evidence_audits)
            self.assertTrue(restored['engine']._legal_evidence_audits[0]['review_required'])

    def test_old_checkpoint_without_evidence_field_restores_with_empty_unverified_audit(self):
        import json
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/session.db'):
            engine=DebateEngineV3('legacy-audit',20,1,'general')
            session_store.save(self._session(engine,'legacy-audit'))
            with session_store.connect() as db:
                payload=db.execute('SELECT payload FROM sessions WHERE id=?',('legacy-audit',)).fetchone()[0]
                data=json.loads(payload)
                del data['engine_state']['_legal_evidence_audits']
                db.execute('UPDATE sessions SET payload=? WHERE id=?',
                           (json.dumps(data), 'legacy-audit'))
            restored=session_store.load('legacy-audit', DebateEngineV3)
            self.assertEqual(restored['engine']._legal_evidence_audits,[])
            from legal.assurance import synthesis_assurance
            self.assertTrue(synthesis_assurance(restored['engine']._legal_evidence_audits)['professional_legal_review_required'])

    def test_malformed_persisted_evidence_is_quarantined_without_data_loss(self):
        import json
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, SESSION_DB_PATH=folder+'/session.db'):
            engine=DebateEngineV3('bad-audit',20,1,'general')
            session_store.save(self._session(engine,'bad-audit'))
            with session_store.connect() as db:
                payload=db.execute('SELECT payload FROM sessions WHERE id=?',('bad-audit',)).fetchone()[0]
                data=json.loads(payload)
                data['engine_state']['_legal_evidence_audits']='not-an-evidence-list'
                db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(data),'bad-audit'))
            with self.assertRaises(session_store.SessionCheckpointError):
                session_store.load('bad-audit',DebateEngineV3)
