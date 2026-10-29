import json
import unittest
from unittest.mock import patch, Mock
import httpx
from provider import MaritacaClient, ProviderError
from config import settings
from engines.debate_engine_v3 import DebateEngineV3, _run_crew
from agents.cluster_definitions import CLUSTERS


class ProviderTests(unittest.TestCase):
    def dispatch(self, response):
        with patch.object(settings, 'MARITACA_API_KEY', 'synthetic-secret'), patch('provider.httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value = response
            result = MaritacaClient().call([{'role': 'user', 'content': 'synthetic'}])
            return result, client.return_value.__enter__.return_value.post

    def test_one_request_and_no_framework_prompt_loop(self):
        llm = Mock()
        llm.call.return_value = '{"result": "ok"}'
        self.assertEqual(_run_crew(CLUSTERS['foundation']['agents'][0], 'Only JSON', llm), '{"result": "ok"}')
        llm.call.assert_called_once()
        self.assertIn('untrusted evidence', llm.call.call_args.args[0][0]['content'])

    def test_transport_matches_documented_chat_endpoint(self):
        content, post = self.dispatch(httpx.Response(200, json={'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason':'stop'}]}))
        self.assertEqual(content, '{"ok":true}')
        post.assert_called_once()
        self.assertTrue(post.call_args.args[0].endswith('/chat/completions'))
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Key synthetic-secret')
        self.assertNotIn('max_retries', post.call_args.kwargs['json'])
        self.assertNotIn('response_format', post.call_args.kwargs['json'])

    def test_failures_are_actionable_and_do_not_leak_response_payloads(self):
        for status, code in ((400,'invalid_request'), (401,'authentication'), (402,'billing'), (403,'permission'), (429,'rate_limit'), (503,'provider_unavailable')):
            with self.assertRaises(ProviderError) as raised:
                self.dispatch(httpx.Response(status, text='private payload synthetic-secret'))
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn('private payload', str(raised.exception))
            self.assertNotIn('synthetic-secret', str(raised.exception))

    def test_missing_key_never_sends(self):
        with patch.object(settings, 'MARITACA_API_KEY', ''), patch('provider.httpx.Client') as client:
            with self.assertRaisesRegex(ProviderError, 'MARITACA_API_KEY'):
                MaritacaClient().call([])
            client.assert_not_called()

    def test_malformed_and_truncated_responses_are_not_certified(self):
        for body, code in (({},'invalid_response'), ({'choices':[{'message': {'content':'partial'},'finish_reason':'length'}]},'truncated')):
            with self.assertRaises(ProviderError) as raised:
                self.dispatch(httpx.Response(200,json=body))
            self.assertEqual(raised.exception.code,code)


class ReviewDepthTests(unittest.IsolatedAsyncioTestCase):
    async def test_focused_workstream_retains_combined_expertise_without_peer_votes(self):
        engine = DebateEngineV3('focused-test',20,1,'general')
        engine.review_depth = 'focused'
        analysis = {'agent':'reviewer','cluster':'foundation','score':6,'reasoning':'Synthetic', 'confidence_level':3}
        summary = {'cluster':'foundation','cluster_name':'Foundation','aggregated_score':6,'confidence_aggregate':3,'classification':'Relevante','summary':'Synthetic'}
        with patch.object(engine, '_run_agent', side_effect=[json.dumps(analysis),json.dumps(summary)]) as run:
            await engine._run_single_cluster('foundation',CLUSTERS['foundation'],'synthetic',1)
        self.assertEqual(run.call_count,2)
        first_config = run.call_args_list[0].args[0]
        self.assertTrue(all(topic in first_config['expertise'] for a in CLUSTERS['foundation']['agents'] for topic in a.get('expertise',[])))

    async def test_provider_failure_stops_queued_calls_and_retains_safe_reason(self):
        engine = DebateEngineV3('auth-test',20,1,'general')
        with patch('engines.debate_engine_v3._run_crew', side_effect=ProviderError('authentication','Update the provider credential')) as call:
            for _ in range(2):
                with self.assertRaisesRegex(ProviderError,'credential'):
                    await engine._run_agent({'role':'Synthetic'},'Synthetic')
        self.assertEqual(call.call_count,1)
        self.assertEqual(engine.execution_metrics['model_tasks'][0]['error_code'],'authentication')


class PlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_full_and_opt_in_focused_have_actual_call_counts(self):
        import main
        from models.schemas import SessionCreateRequest
        with patch.object(settings, 'ACTIVE_CLUSTERS', ','.join(CLUSTERS)):
            for depth, calls, agents in (('full',47,20),('focused',12,5)):
                result = await main.create_session(SessionCreateRequest(review_depth=depth), main.Principal('https://identity.example/', 'test-lawyer'))
                self.assertEqual(result.config['initial_model_calls'],calls)
                self.assertEqual(result.config['num_agents'],agents)
                self.assertEqual(main.sessions[result.session_id]['engine'].review_depth,depth)
