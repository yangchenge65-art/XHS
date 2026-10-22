import json
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from hotdesk.core import Store, SourceError
from hotdesk.openai_research import OpenAIResearch
from hotdesk.settings import Settings


NOW = datetime(2026, 10, 22, 10, tzinfo=ZoneInfo('Asia/Shanghai'))


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + '/test.db')
        self.settings = Settings(self.tmp.name, environ={'HOTDESK_OPENAI_API_KEY': 'test-key', 'HOTDESK_GPT_COST_CNY': '.5'})
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def response(self, url='https://www.douyin.com/video/123'):
        item = dict(platform='douyin', title='KPL 决赛', content='来源摘要', url=url,
                    event_key='kpl决赛', published_at='2026-10-22T08:00:00+08:00', reason='当天来源', hook='开头')
        return dict(status='completed', output=[dict(type='web_search_call', status='completed', action=dict(
            sources=[dict(type='url', url='https://www.douyin.com/video/123')])), dict(type='message', content=[dict(
                type='output_text', text=json.dumps({'items': [item]}), annotations=[])])])

    def engine(self, response):
        def transport(path, key='', body=None, timeout=20):
            self.calls.append((path, body))
            return response
        return OpenAIResearch(self.settings, self.store, now=lambda: NOW, transport=transport)

    def test_real_web_search_request_and_sources_not_invented(self):
        engine = self.engine(self.response())
        rows = engine.discover()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.store.spent(NOW), .5)
        request = self.calls[0][1]
        self.assertEqual(request['model'], 'gpt-5.1')
        self.assertEqual(request['tools'][0]['type'], 'web_search')
        self.assertFalse(request['store'])
        self.assertEqual(request['max_tool_calls'], 3)
        self.assertEqual(self.engine(self.response(url='https://evil.example/fake')).discover(), [])

    def test_no_search_or_incomplete_response_is_failure(self):
        response = self.response()
        response['output'] = response['output'][1:]
        with self.assertRaises(SourceError):
            self.engine(response).discover()
        response = self.response()
        response['status'] = 'incomplete'
        with self.assertRaises(SourceError):
            self.engine(response).discover()

    def test_missing_key_or_budget_never_calls_remote(self):
        self.settings = Settings(self.tmp.name, environ={})
        with self.assertRaises(SourceError):
            self.engine(self.response()).discover()
        self.assertEqual(self.calls, [])
        self.settings = Settings(self.tmp.name, environ={'HOTDESK_OPENAI_API_KEY': 'test-key', 'HOTDESK_GPT_COST_CNY': '.5'})
        self.store.reserve(NOW, 30)
        with self.assertRaises(SourceError):
            self.engine(self.response()).discover()
        self.assertEqual(self.calls, [])

    def test_saved_settings_encrypt_key_and_never_return_it(self):
        settings = Settings(self.tmp.name, environ={}, protect=lambda value: 'encrypted:' + value[::-1], unprotect=lambda value: value[10:][::-1])
        public = settings.save(api_key='a-private-key', cost='.75')
        self.assertTrue(public['configured'])
        self.assertNotIn('a-private-key', json.dumps(public))
        self.assertNotIn('a-private-key', settings.path.read_text())
        self.assertEqual(settings.key(), 'a-private-key')
        settings.save(cost='1')
        self.assertEqual(settings.key(), 'a-private-key')
        with self.assertRaises(ValueError):
            settings.save(cost='-1')
        self.assertEqual(settings.public()['cost'], '1')


if __name__ == '__main__':
    unittest.main()
