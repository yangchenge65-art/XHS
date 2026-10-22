"""Persistent daily 4/3/2 edition and single-slot replacements."""
import hashlib
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .core import SourceError, TZ, clock, decorate, export_excel, safe_url

QUOTAS = {'douyin': 4, 'xiaohongshu': 3, 'news': 2}


def topic_key(value):
    return re.sub(r'[\W_]+', '', str(value)).casefold()


def url_key(value):
    u = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(u.query) if not k.startswith('utm_') and k not in ('xsec_token', 'xsec_source')]
    return urlunsplit((u.scheme, u.netloc.lower(), u.path.rstrip('/'), urlencode(sorted(query)), ''))


class Briefing:
    def __init__(self, store, researcher, data_dir, now=clock, demo=False):
        self.store, self.researcher, self.now = store, researcher, now
        self.data_dir, self.demo = Path(data_dir), demo
        self.lock = threading.RLock()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS editions(day TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def day(self):
        return self.now().astimezone(TZ).date().isoformat()

    def load(self):
        with self.store.connect() as db:
            row = db.execute('SELECT payload FROM editions WHERE day=?', (self.day(),)).fetchone()
        return json.loads(row[0]) if row else None

    def report(self):
        edition = self.load() or dict(items=[], pool=[], rejected=[], errors=[], generated_at=None)
        missing = {p: count - sum(i['platform'] == p for i in edition['items']) for p, count in QUOTAS.items()}
        return dict(items=edition['items'], errors=edition['errors'], missing=missing, quotas=QUOTAS,
                    status='partial' if any(missing.values()) or edition['errors'] else 'ok',
                    demo=self.demo, generated_at=edition['generated_at'], cached=False, engine=edition.get('engine') or getattr(self.researcher, 'engine_name', 'GPT-5.1'),
                    coverage=('虚构示例，只演示 4/3/2 配额和换一条，不是真实事件。' if self.demo else
                              '今日精选：抖音 4 / 小红书 3 / 大众事件 2。公开联网检索线索；不代表完整平台热榜。'
                              '近七天来源，优先最新；不足配额不编造补齐。开头建议需核实。'))

    def candidates(self, rows):
        candidates = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or row.get('platform') not in QUOTAS or not row.get('title'):
                continue
            url = safe_url(row.get('url'))
            if not url:
                continue
            platform, title = row['platform'], str(row['title'])[:200]
            key = topic_key(row.get('event_key') or title)
            if not key:
                continue
            identity = hashlib.sha256((platform + '|' + key + '|' + url_key(url)).encode()).hexdigest()[:24]
            if identity in seen:
                continue
            seen.add(identity)
            item = decorate(dict(row, title=title, url=url), platform, days=0, consecutive=0)
            item.update(id=identity, event_key=key, kind='公开检索线索',
                        generator=getattr(self.researcher, 'engine_name', 'GPT-5.1'),
                        reason=str(row.get('reason') or '公开来源线索；未核实上榜或具体讨论量')[:1000],
                        hook=str(row.get('hook') or item['hook'])[:500],
                        observed_at=self.now().isoformat())
            candidates.append(item)
        return candidates

    @staticmethod
    def available(pool, selected, rejected, category):
        used = {i['event_key'] for i in selected} | set(rejected)
        urls = {url_key(i['url']) for i in selected} | {value[4:] for value in rejected if value.startswith('url:')}
        return [i for i in pool if i['platform'] == category and i['event_key'] not in used and url_key(i['url']) not in urls]

    def save(self, edition):
        edition['generated_at'] = self.now().isoformat()
        engines = list(dict.fromkeys(i.get('generator', getattr(self.researcher, 'engine_name', 'GPT-5.1')) for i in edition['items']))
        edition['engine'] = ' / '.join(engines) if engines else getattr(self.researcher, 'engine_name', 'GPT-5.1')
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO editions VALUES(?,?)', (self.day(), json.dumps(edition, ensure_ascii=False)))
        target = self.data_dir / 'reports' / ('demo' if self.demo else 'real') / (self.day() + '.xlsx')
        temp = target.with_suffix('.tmp.xlsx')
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp.write_bytes(self.excel())
            os.replace(temp, target)
        except OSError:
            edition['errors'].append(dict(platform='system', message='Excel 自动保存失败（文件可能被占用）；素材已保存在数据库，可在网页重新导出'))
            with self.store.connect() as db:
                db.execute('INSERT OR REPLACE INTO editions VALUES(?,?)', (self.day(), json.dumps(edition, ensure_ascii=False)))
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def generate(self):
        with self.lock:
            edition = self.load() or dict(items=[], pool=[], rejected=[], errors=[], generated_at=None)
            if len(edition['items']) == sum(QUOTAS.values()):
                return self.report()
            edition['errors'] = []
            try:
                error = self.researcher.ready()
                if error:
                    raise SourceError(error)
                edition['pool'].extend(self.candidates(self.researcher.discover(excluded=edition['rejected'])))
                for platform, quota in QUOTAS.items():
                    for number in range(1, quota + 1):
                        slot = f'{platform}-{number}'
                        if any(i.get('slot') == slot for i in edition['items']):
                            continue
                        options = self.available(edition['pool'], edition['items'], edition['rejected'], platform)
                        if options:
                            edition['items'].append(dict(options[0], slot=slot))
            except SourceError as exc:
                edition['errors'].append(dict(platform='research', message=str(exc)))
            edition['items'].sort(key=lambda i: (list(QUOTAS).index(i['platform']), i['slot']))
            self.save(edition)
            return self.report()

    def replace(self, slot, expected_id):
        with self.lock:
            edition = self.load()
            if not edition:
                raise ValueError('请先生成今日精选')
            index = next((n for n, i in enumerate(edition['items']) if i['slot'] == slot), None)
            if index is None or not expected_id or edition['items'][index]['id'] != expected_id:
                raise ValueError('这条素材已变化，请刷新后重试')
            original = edition['items'][index]
            rejected = edition['rejected'] + [original['event_key'], 'url:' + url_key(original['url'])]
            edition['errors'] = []
            try:
                options = self.available(edition['pool'], edition['items'], rejected, original['platform'])
                if not options:
                    error = self.researcher.ready()
                    if error:
                        raise SourceError(error)
                    excluded = list(dict.fromkeys(rejected + [i['event_key'] for i in edition['items']]))
                    edition['pool'].extend(self.candidates(self.researcher.discover(category=original['platform'], excluded=excluded)))
                    options = self.available(edition['pool'], edition['items'], rejected, original['platform'])
                if not options:
                    raise SourceError('没有找到新的有来源素材，原内容已保留；可稍后重试')
                edition['items'][index] = dict(options[0], slot=slot)
                edition['rejected'] = rejected
            except SourceError as exc:
                edition['errors'].append(dict(platform='research', message=str(exc)))
            self.save(edition)
            return self.report()

    def excel(self):
        result = self.report()
        for platform, missing in result['missing'].items():
            if missing:
                result['errors'].append(dict(platform=platform, message=f'当前缺少 {missing} 条，不用无来源素材补齐'))
        return export_excel(result, demo=self.demo)
