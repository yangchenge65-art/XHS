import json
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace

from hotdesk.core import Store, SourceError
from hotdesk.settings import Settings
from hotdesk.codex_research import CodexResearch, codex_items


NOW = datetime(2026, 10, 22, 10, tzinfo=ZoneInfo('Asia/Shanghai'))


def events():
    item = dict(platform='douyin', title='有来源的话题', content='内容', url='https://www.douyin.com/video/123',
                published_at='2026-10-22T08:00:00+08:00', event_key='独立事件', reason='来源支持', hook='开头')
    return [dict(type='item.completed', item=dict(type='web_search', action=dict(type='open_page', url=item['url']))),
            dict(type='item.completed', item=dict(type='agent_message', text=json.dumps({'items': [item]}))),
            dict(type='turn.completed', usage={})]


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + '/test.db')
        self.settings = Settings(self.tmp.name, environ={})
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[-2:] == ['login', 'status']:
            return SimpleNamespace(returncode=0, stdout='', stderr='Logged in using ChatGPT')
        return SimpleNamespace(returncode=0, stdout='\n'.join(json.dumps(e) for e in events()), stderr='')

    def engine(self, runner=None):
        return CodexResearch(self.settings, self.store, self.tmp.name, now=lambda: NOW,
                             command=['node', 'codex.js'], runner=runner or self.runner)

    def test_subscription_auth_only_and_no_api_cost_reservation(self):
        engine = self.engine()
        rows = engine.discover()
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.store.spent(NOW), 0)
        args, kwargs = self.calls[-1]
        self.assertIn('--sandbox', args)
        self.assertIn('read-only', args)
        self.assertIn('features.shell_tool=false', args)
        self.assertIn('web_search="live"', args)
        self.assertFalse(kwargs.get('shell', False))
        self.assertNotIn('OPENAI_API_KEY', kwargs['env'])

    def test_api_login_is_rejected_and_daily_cli_calls_are_limited(self):
        def api_login(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout='', stderr='Logged in using an API key')
        self.assertIn('ChatGPT', self.engine(api_login).ready())
        engine = self.engine()
        for _ in range(8):
            engine.discover()
        with self.assertRaises(SourceError):
            engine.discover()

    def test_no_search_or_uncited_urls_do_not_become_live_items(self):
        with self.assertRaises(SourceError):
            codex_items(events()[1:], NOW)
        data = events()
        data[0]['item']['action']['url'] = 'https://example.com/different'
        self.assertEqual(codex_items(data, NOW), [])
        data = events()
        data[-1]['type'] = 'turn.failed'
        with self.assertRaises(SourceError):
            codex_items(data, NOW)


if __name__ == '__main__':
    unittest.main()
