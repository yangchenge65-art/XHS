"""Endpoint definitions checked against TikHub's official Python SDK, 2026-10-22.

No live paid requests have been validated without a user-supplied API key.
"""
import json
import os
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .core import SourceError, safe_url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url, key='', body=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'Hotdesk/0.1'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    payload = None
    if body is not None:
        payload = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with build_opener(NoRedirect()).open(Request(url, data=payload, headers=headers), timeout=20) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise SourceError('数据源响应过大，请缩小结果范围')
        data = json.loads(raw)
    except HTTPError as exc:
        raise SourceError(f'数据源返回 HTTP {exc.code}，请检查授权、余额及网络设置') from None
    except (URLError, TimeoutError, OSError):
        raise SourceError('无法连接数据源，请检查网络及域名许可') from None
    except (ValueError, UnicodeError):
        raise SourceError('数据源未返回有效 JSON') from None
    if isinstance(data, dict) and str(data.get('code', 200)) not in ('0', '200'):
        raise SourceError('数据源报告业务失败，请检查服务控制台（不缓存为成功）')
    return data


def normalize(payload, platform, hot=False):
    items = []
    recognized = False

    def walk(node):
        nonlocal recognized
        if isinstance(node, list):
            recognized = True
            for value in node:
                walk(value)
            return
        if not isinstance(node, dict):
            return
        title = node.get('word') if hot else None
        identifier = node.get('aweme_id') or node.get('note_id')
        if not identifier and node.get('id') and ('title' in node or 'desc' in node):
            identifier = node['id']
        if not title and identifier:
            title = node.get('title') or node.get('display_title') or node.get('desc')
        if title:
            recognized = True
            title = str(title)
            url = safe_url(node.get('share_url') or node.get('url'))
            if not url:
                if platform == 'douyin':
                    url = ('https://www.douyin.com/video/' + quote(str(identifier), safe='')) if identifier else 'https://www.douyin.com/search/' + quote(title, safe='')
                elif identifier:
                    url = 'https://www.xiaohongshu.com/explore/' + quote(str(identifier), safe='')
                    if node.get('xsec_token'):
                        url += '?' + urlencode({'xsec_token': node['xsec_token'], 'xsec_source': 'pc_search'})
                else:
                    url = 'https://www.xiaohongshu.com/search_result?' + urlencode({'keyword': title})
            items.append(dict(id=str(identifier or title), title=title, content=str(node.get('desc') or title), url=url,
                              published_at=node.get('create_time') or node.get('time') or node.get('publish_time'),
                              rank=node.get('position') if hot else None,
                              heat=node.get('hot_value') if hot else None))
            return
        for key, value in node.items():
            if key in ('data', 'items', 'notes', 'note', 'note_card', 'aweme_info', 'aweme_list', 'word_list', 'result', 'results'):
                walk(value)

    walk(payload)
    if not recognized:
        raise SourceError('数据源响应结构无法识别，需要更新适配器；未当作空结果保存')
    unique = {i['id']: i for i in items}
    return list(unique.values())


class TikHub:
    def __init__(self, key=None, cost=None, xhs_feed=None):
        self.key = os.getenv('TIKHUB_API_KEY', '') if key is None else key
        self.cost = os.getenv('HOTDESK_CALL_COST_CNY', '0') if cost is None else cost
        self.xhs_feed = os.getenv('HOTDESK_XHS_HOT_FEED', '') if xhs_feed is None else xhs_feed

    def ready(self, platform, kind):
        if platform == 'xiaohongshu' and kind == 'hot':
            if not self.xhs_feed:
                return '小红书热榜数据源未接入；需要配置已验证的标准 JSON 榜单接口'
            if not safe_url(self.xhs_feed) or urlsplit(self.xhs_feed).scheme != 'https':
                return '小红书热榜接口必须使用 HTTPS，不能在 URL 中放密钥'
        elif not self.key:
            return '未配置 TikHub API 密钥；当前不会发起付费请求'
        try:
            amount = Decimal(str(self.cost))
            if not amount.is_finite() or not 0 < amount <= 30:
                raise ValueError()
        except (InvalidOperation, ValueError):
            return '请先配置单次请求的人民币费用上界 HOTDESK_CALL_COST_CNY（大于 0，不超过 30）'
        return None

    def fetch(self, platform, keyword=None):
        error = self.ready(platform, 'search' if keyword else 'hot')
        if error:
            raise SourceError(error)
        if platform == 'xiaohongshu' and not keyword:
            # Independent feed; TikHub's key is never sent to this URL.
            payload = get_json(self.xhs_feed)
            rows = payload.get('items') if isinstance(payload, dict) else None
            if not isinstance(rows, list) or any(not isinstance(i, dict) or not i.get('title') for i in rows):
                raise SourceError('小红书榜单 JSON 必须包含 items 数组及每条的 title 字段')
            return [dict(id=i.get('id') or i['title'], title=str(i['title']), content=str(i.get('content') or i['title']),
                         url=safe_url(i.get('url')), rank=i.get('rank'), heat=i.get('heat'), published_at=None) for i in rows]
        root = 'https://api.tikhub.io/api/v1/'
        if not keyword:
            data = get_json(root + 'douyin/web/fetch_hot_search_result', self.key)
        elif platform == 'douyin':
            data = get_json(root + 'douyin/search/fetch_general_search_v1', self.key, dict(
                keyword=keyword, cursor=0, sort_type='1', publish_time='7',
                filter_duration='0', content_type='0', search_id='', backtrace=''))
        else:
            data = get_json(root + 'xiaohongshu/app_v2/search_notes?' + urlencode(dict(
                keyword=keyword, page=1, sort_type='popularity_descending', note_type='不限', time_filter='一周内')), self.key)
        return normalize(data, platform, hot=not keyword)
