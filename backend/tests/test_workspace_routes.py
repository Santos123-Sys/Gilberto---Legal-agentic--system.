"""Protected wire projection and persisted-export integration regressions."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx
import main
from config import settings
from security.oidc import Principal


class WorkspaceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, SESSION_DB_PATH=tmp.name + '/sessions.db')
        env.start(); self.addCleanup(env.stop)
        mode = patch.object(settings, 'AUTH_MODE', 'oidc')
        mode.start(); self.addCleanup(mode.stop)
        main.sessions.clear()
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(issuer='test', subject='owner')
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test')
        self.addAsyncCleanup(self.client.aclose)
        response = await self.client.post('/api/sessions', json={'num_rounds': 1})
        self.sid = response.json()['session_id']
        self.session = main.sessions[self.sid]
        self.path = '/api/sessions/' + self.sid

    async def test_same_authorized_journal_exact_cursor_and_replay(self):
        self.session['status'] = 'completed'
        for event in ({'type': 'ROUND_START', 'round': 1}, {'type': 'AGENT_VOTE_CAST',
                'round': 1, 'cluster': 'foundation', 'voter': 'Contract Classifier', 'scores': {'score': 4}}):
            main._append_event(self.session, event)
        native = await self.client.get(self.path + '/stream?cursor=1')
        projected = await self.client.get(self.path + '/stream?cursor=1&protocol=ag-ui')
        events = [json.loads(line[6:]) for line in projected.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(events[0]['type'], 'STATE_SNAPSHOT')
        self.assertEqual(events[0]['snapshot']['execution_state'], 'COMPLETED')
        self.assertEqual(events[0]['metadata']['journalWatermark'], 2)
        self.assertEqual(events[1]['value'], self.session['events'][1])
        self.assertEqual(events[1]['value']['agent_id'], 'foundation:specialist:contract-classifier')
        self.assertEqual(events[-1]['name'], 'gilberto.STREAM_END')
        self.assertIn('id: 2\n', projected.text)
        self.assertIn('id: 2\n', native.text)
        self.assertEqual((await self.client.get(self.path + '/stream?protocol=invalid')).status_code, 422)
        self.assertEqual((await self.client.get(self.path + '/stream?cursor=99&protocol=ag-ui')).status_code, 409)
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(issuer='test', subject='other')
        self.assertEqual((await self.client.get(self.path + '/stream?cursor=1&protocol=ag-ui')).status_code, 404)

    async def test_status_uses_actual_roster_and_export_cannot_fail_checkpoint(self):
        response = await self.client.get(self.path + '/status')
        body = response.json()
        self.assertEqual([c['id'] for c in body['config']['agent_roster']],
                         [c['id'] for c in body['config']['active_clusters']])
        self.assertIn('coordination_roster', body['config'])
        telemetry = Mock(enabled=True)
        telemetry.submit.side_effect = RuntimeError('confidential error')
        with patch.object(main.app.state, 'telemetry', telemetry, create=True):
            main._append_event(self.session, {'type': 'ROUND_START', 'round': 1})
            main._checkpoint(self.session)
            self.assertIsNotNone(self.session['last_checkpoint_at'])
            telemetry.submit.assert_called_once()
        with patch.object(main.session_store, 'save', side_effect=OSError('disk unavailable')):
            with patch.object(main.app.state, 'telemetry', telemetry, create=True):
                telemetry.reset_mock()
                with self.assertRaises(OSError):
                    main._checkpoint(self.session)
                telemetry.submit.assert_not_called()
