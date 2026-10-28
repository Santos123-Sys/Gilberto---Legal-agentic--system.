"""Synthetic API/orchestration regressions; never sends paid model calls."""
import asyncio
import json
import math
import unittest
from unittest.mock import patch
import httpx
import main
from config import settings
from engines.debate_engine_v3 import ReanalysisRequested, _safe_json
from scoring import aggregate_clusters, weighted_median


def summary(cid='foundation', score=6, confidence=4):
    return {'raw': '{}', 'parsed': {'cluster': cid, 'cluster_name': cid,
            'aggregated_score': score, 'confidence_aggregate': confidence,
            'classification': 'Relevante', 'summary': 'Synthetic contract review',
            'key_findings': [], 'risk_flags': [], 'agent_count': 4}}


class ScoringTests(unittest.TestCase):
    def test_weighted_median_sorts_by_score_and_applies_weights(self):
        self.assertEqual(weighted_median([(9, 1), (1, 5), (8, 1)]), 1)
        self.assertEqual(weighted_median([(2, 3), (8, 3)]), 5)
        self.assertEqual(weighted_median([(8, 2), (1, 1), (4, 2)]), 4)

    def test_invalid_scores_fail(self):
        for pairs in ([], [(math.nan, 1)], [(5, 0)], [(11, 1)]):
            with self.assertRaises(ValueError):
                weighted_median(pairs)

    def test_classification_boundaries(self):
        for score, label in ((4.9, 'Aceitável'), (5, 'Relevante'), (8, 'Crítico')):
            self.assertEqual(aggregate_clusters({'a': summary(score=score)})['final_classification'], label)

    def test_invalid_json_shapes_fail(self):
        for raw in ('[]', 'null', 'not JSON', '{"score": NaN}'):
            with self.assertRaises(ValueError):
                _safe_json(raw)
        self.assertEqual(_safe_json('```json\n{"score":2}\n```'), {'score': 2})


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.sessions.clear()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test')
        response = await self.client.post('/api/sessions', json={'num_rounds': 1})
        self.assertEqual(response.status_code, 200, response.text)
        self.sid = response.json()['session_id']
        self.session = main.sessions[self.sid]
        self.engine = self.session['engine']

    async def asyncTearDown(self):
        for session in main.sessions.values():
            task = session.get('task')
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await self.client.aclose()

    def gate(self, cluster='foundation'):
        record = self.engine.gate_evaluator.record_trigger({'gate_number': 1, 'affected_cluster': cluster})
        self.session['pending_gates'].append(record['gate_id'])
        self.session['status'] = 'awaiting_gate'
        return record

    async def decide(self, gate, decision='approve', **extra):
        return await self.client.post(f'/api/sessions/{self.sid}/gate-decision', json={
            'session_id': self.sid, 'gate_number': 1, 'gate_id': gate['gate_id'],
            'human_review_id': 'test', 'decision': decision,
            'reasoning': 'Please recheck termination.', **extra})

    async def test_acceptance_requires_finished_review_and_is_idempotent(self):
        for status in ('created', 'running', 'error', 'awaiting_gate', 'awaiting_feedback'):
            self.session['status'] = status
            self.assertEqual((await self.client.post(f'/api/sessions/{self.sid}/accept')).status_code, 409)
        self.engine.master_summaries = [{'parsed': {'final_score': 6, 'final_classification': 'Relevante'}}]
        self.session['status'] = 'awaiting_feedback'
        for _ in range(2):
            self.assertEqual((await self.client.post(f'/api/sessions/{self.sid}/accept')).status_code, 200)

    async def test_duplicate_number_resolves_only_exact_review(self):
        first, second = self.gate(), self.gate('compliance')
        self.assertNotEqual(first['gate_id'], second['gate_id'])
        self.assertEqual(len((await self.client.get(f'/api/sessions/{self.sid}/gates')).json()['pending_gates']), 2)
        self.assertEqual((await self.decide(first)).status_code, 200)
        self.assertEqual(self.session['pending_gates'], [second['gate_id']])
        self.assertEqual((await self.decide(first)).status_code, 409)
        self.assertEqual((await self.decide(second)).status_code, 200)
        self.assertEqual(self.session['status'], 'running')
        self.assertEqual((await self.client.post(f'/api/sessions/{self.sid}/accept')).status_code, 409)

    async def test_ambiguous_or_wrong_session_review_is_rejected(self):
        gate = self.gate()
        self.gate('compliance')
        response = await self.decide(gate, gate_id=None)
        self.assertEqual(response.status_code, 409)
        self.assertEqual((await self.decide(gate, session_id='wrong')).status_code, 409)

    async def test_override_preserves_original_model_assessment(self):
        self.engine.master_summaries = [{'parsed': {'final_score': 6, 'final_classification': 'Relevante'}}]
        gate = self.gate()
        self.assertEqual((await self.decide(gate, 'override')).status_code, 422)
        self.assertEqual((await self.decide(gate, 'override', override_score=8)).status_code, 200)
        parsed = self.engine.master_summaries[-1]['parsed']
        self.assertEqual(parsed['final_classification'], 'Crítico')
        self.assertEqual(parsed['model_assessment']['final_score'], 6)
        self.assertTrue(any(g['gate_number'] == 3 for g in self.engine.get_pending_gates()))
        self.assertEqual(self.session['status'], 'awaiting_gate')

    async def test_reanalysis_consumed_once_and_limit_enforced(self):
        gate = self.gate()
        self.assertEqual((await self.decide(gate, 'request_reanalysis')).status_code, 200)
        with self.assertRaises(ReanalysisRequested):
            await self.engine._wait_for_gate_decisions()
        await self.engine._wait_for_gate_decisions()
        gate = self.gate()
        self.session['feedback_rounds'] = settings.MAX_FEEDBACK_ROUNDS
        self.assertEqual((await self.decide(gate, 'request_reanalysis')).status_code, 409)
        self.assertEqual(gate['status'], 'pending')

    async def test_event_history_does_not_mutate_after_gate_resolution(self):
        gate = self.gate()
        main._append_event(self.session, {'type': 'GATE_TRIGGERED', 'record': gate})
        await self.decide(gate)
        self.assertEqual(self.session['events'][0]['record']['status'], 'pending')

    async def test_feedback_rejects_concurrent_execution(self):
        self.session['status'] = 'running'
        response = await self.client.post(f'/api/sessions/{self.sid}/feedback', json={'feedback': 'Please review termination'})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.session['task'])

    async def test_corrupted_checkpoint_returns_safe_service_error(self):
        with patch.object(main.session_store, 'load', side_effect=main.session_store.SessionCheckpointError('private content /data/path')):
            response = await self.client.get('/api/sessions/unknown/status')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private content', response.text)
        self.assertNotIn('/data/path', response.text)

    async def test_round_jurisdiction_cursor_and_upload_limits(self):
        for body in ({'num_rounds': 0}, {'num_rounds': 4}, {'jurisdiction': 'CH'}):
            self.assertEqual((await self.client.post('/api/sessions', json=body)).status_code, 422)
        for cursor, status in ((-1, 422), (99, 409)):
            self.assertEqual((await self.client.get(f'/api/sessions/{self.sid}/stream?cursor={cursor}')).status_code, status)
        with patch.object(settings, 'MAX_UPLOAD_BYTES', 8):
            response = await self.client.post(f'/api/sessions/{self.sid}/start', files={'document': ('a.txt', b'0123456789')})
            self.assertEqual(response.status_code, 413)
        self.assertEqual(self.session['status'], 'created')

    async def test_cluster_failure_retains_partial_work_and_never_completes(self):
        async def run(cid, *_):
            if cid == 'foundation':
                return summary()
            raise ValueError('private provider payload')
        with patch.object(self.engine, '_run_single_cluster', side_effect=run):
            await main._run_analysis_bg(self.sid, 'Synthetic document')
        self.assertEqual(self.session['status'], 'error')
        self.assertIn('foundation', self.engine.cluster_summaries)
        events = self.session['events']
        self.assertFalse(any(event['type'] == 'DEBATE_COMPLETE' for event in events))
        self.assertNotIn('private provider payload', self.session['error'])
        self.assertEqual([e['event_id'] for e in events], list(range(1, len(events) + 1)))

    async def test_invalid_feedback_route_is_rejected(self):
        self.engine.cluster_summaries = {'foundation': summary()}
        with patch.object(self.engine, '_run_agent', return_value='{"target_cluster":"invented"}'):
            await main._run_analysis_bg(self.sid, 'Synthetic document', 'Review termination')
        self.assertEqual(self.session['status'], 'error')
        self.assertFalse(any(self.engine.feedback_agents.values()))

    async def test_final_score_cannot_be_invented_by_model(self):
        self.engine.cluster_summaries = {'foundation': summary(score=9)}
        raw = json.dumps({'final_score': 0, 'final_classification': 'Aceitável', 'confidence': 4, 'reasoning': 'Test'})
        with patch.object(self.engine, '_run_agent', return_value=raw):
            result = await self.engine._run_master_manager(1)
        self.assertEqual(result['parsed']['final_score'], 9)
        self.assertEqual(result['parsed']['final_classification'], 'Crítico')

    async def test_budget_prevents_dispatch(self):
        self.engine.execution_metrics['model_calls'] = settings.MAX_MODEL_CALLS
        with patch('engines.debate_engine_v3._run_crew') as crew:
            with self.assertRaisesRegex(RuntimeError, 'budget'):
                await self.engine._run_agent({}, 'prompt')
            crew.assert_not_called()

    async def test_reanalysis_runner_really_executes_revision(self):
        async def initial(_):
            raise ReanalysisRequested('Recheck termination')
            yield
        async def revision(feedback, _):
            self.assertIn('termination', feedback)
            yield {'type': 'DEBATE_COMPLETE'}
        with patch.object(self.engine, 'run_debate', side_effect=initial), patch.object(self.engine, 'process_feedback', side_effect=revision) as revised:
            await main._run_analysis_bg(self.sid, 'Synthetic document')
        revised.assert_called_once()
        self.assertEqual(self.session['feedback_rounds'], 1)
        self.assertEqual(self.session['status'], 'awaiting_feedback')

class RunBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_run_waits_for_every_review_and_uses_new_ids_each_round(self):
        main.sessions.clear()
        created = await main.create_session(main.SessionCreateRequest(num_rounds=2))
        sid = created.session_id
        session = main.sessions[sid]
        engine = session['engine']
        async def cluster(cid, *_):
            return summary(cid, score=9, confidence=2)
        async def adversarial(*_):
            engine.devil_advocate_output = {'parsed': {'sad_score': 1, 'gap_severity_score': 0}, 'raw': '{}'}
        model = json.dumps({'final_score': 0, 'final_classification': 'Aceitável', 'confidence': 4, 'reasoning': 'Test'})
        seen = set()
        with patch.object(settings, 'ACTIVE_CLUSTERS', 'foundation'), patch.object(engine, '_run_single_cluster', side_effect=cluster), patch.object(engine, '_run_devils_advocate', side_effect=adversarial), patch.object(engine, '_run_agent', return_value=model):
            task = asyncio.create_task(main._run_analysis_bg(sid, 'Synthetic contract'))
            session['task'] = task
            for round_number in (1, 2):
                for _ in range(200):
                    if session['status'] == 'awaiting_gate' and engine.current_round == round_number:
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(session['status'], 'awaiting_gate')
                pending = list(engine.get_pending_gates())
                self.assertEqual(len(pending), 2)
                self.assertFalse(seen.intersection(g['gate_id'] for g in pending))
                for gate in pending:
                    seen.add(gate['gate_id'])
                    await main.submit_gate_decision(sid, main.GateDecisionRequest(
                        session_id=sid, gate_number=gate['gate_number'], gate_id=gate['gate_id'],
                        human_review_id='test', decision='approve', reasoning='Reviewed the source'))
                self.assertEqual(session['status'], 'running')
            await asyncio.wait_for(task, timeout=2)
        self.assertEqual(session['status'], 'awaiting_feedback')
        self.assertEqual(len(session['rounds']), 2)
        self.assertEqual((await main.accept_result(sid))['status'], 'completed')

    async def test_timeout_aborts_queued_work_without_dispatch(self):
        engine = main.DebateEngineV3('timeout', 20, 1, 'general')
        async def slow_provider(*args):
            await asyncio.sleep(0.05)
            return '{}'
        with patch.object(settings, 'LLM_REQUEST_TIMEOUT_SECONDS', 0.001), patch('engines.debate_engine_v3.asyncio.to_thread', side_effect=slow_provider):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                await engine._run_agent({'role': 'test'}, 'small prompt')
        with patch('engines.debate_engine_v3._run_crew') as crew:
            with self.assertRaisesRegex(RuntimeError, 'stopped'):
                await engine._run_agent({'role': 'test'}, 'small prompt')
            crew.assert_not_called()
        self.assertEqual(engine.execution_metrics['model_tasks'][0]['status'], 'timed_out')


if __name__ == '__main__':
    unittest.main()
