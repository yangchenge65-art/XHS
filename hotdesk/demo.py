"""Entirely fictional fixtures; separate from the real store and network."""
from datetime import timedelta
from urllib.parse import quote, urlencode


class Demo:
    cost = '0'

    def __init__(self, now):
        self.now = now

    def ready(self, platform, kind):
        return None

    def fetch(self, platform, keyword=None):
        titles = ([f'{keyword} · 赛后讨论（示例）', f'{keyword} · 名场面回顾（示例）', f'{keyword} · 网友二创（示例）']
                  if keyword else ['KPL 决赛名场面（示例）', '肖战舞台细节讨论（示例）', '这段话怎么又火了（示例）', '打工人的周末仪式感（示例）'])
        return [dict(id=title, title=title,
                     content='虚构示例，仅演示素材整理流程。这里会展示事件摘要、语境和可切入的角度；不代表真实新闻或榜单。',
                     url=('https://www.douyin.com/search/' + quote(title.replace('（示例）', '')) if platform == 'douyin'
                          else 'https://www.xiaohongshu.com/search_result?' + urlencode({'keyword': title.replace('（示例）', '')})),
                     rank=None if keyword else index + 2,
                     published_at=(self.now() - timedelta(days=index % 3, hours=1)).isoformat(), heat=None)
                for index, title in enumerate(titles)]
