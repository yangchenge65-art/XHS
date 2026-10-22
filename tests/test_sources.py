import unittest
from hotdesk.providers import TikHub, normalize
from hotdesk.core import SourceError


class Providers(unittest.TestCase):
    def test_douyin_hot_and_search_shapes(self):
        hot = normalize({'data': {'data': {'word_list': [
            {'word': 'KPL 决赛', 'position': 1, 'hot_value': 20000} ]}}}, 'douyin', hot=True)
        self.assertEqual(hot[0]['rank'], 1)
        self.assertIn('douyin.com/search/', hot[0]['url'])
        search = normalize({'data': {'data': [{'aweme_info': {
            'aweme_id': '123', 'desc': 'KPL 决赛', 'create_time': 1792540800}}]}}, 'douyin')
        self.assertEqual(len(search), 1)
        self.assertIn('/video/123', search[0]['url'])

    def test_xhs_notes_and_unknown_payload(self):
        rows = normalize({'data': {'data': {'items': [{'note': {
            'id': 'abc', 'title': '决赛日记', 'desc': '内容', 'time': 1792540800000,
            'xsec_token': 'public-note-token'}}]}}}, 'xiaohongshu')
        self.assertEqual(rows[0]['title'], '决赛日记')
        self.assertIn('xsec_token=', rows[0]['url'])
        with self.assertRaises(SourceError):
            normalize({'data': {'something_changed': True}}, 'xiaohongshu')
        self.assertEqual(normalize({'data': {'items': []}}, 'xiaohongshu'), [])

    def test_missing_key_price_and_xhs_feed_are_explicit(self):
        source = TikHub(key='', cost='0')
        self.assertIn('密钥', source.ready('douyin', 'hot'))
        source = TikHub(key='test', cost='0')
        self.assertIn('费用', source.ready('douyin', 'hot'))
        source = TikHub(key='test', cost='.1')
        self.assertIn('小红书热榜', source.ready('xiaohongshu', 'hot'))
        self.assertIsNone(source.ready('xiaohongshu', 'search'))


if __name__ == '__main__':
    unittest.main()
