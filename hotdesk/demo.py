"""Entirely fictional fixtures; separate from the real store and network."""
from datetime import timedelta
from urllib.parse import quote, urlencode
from uuid import uuid4


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


class DemoResearch:
    engine_name = '虚构示例（未调用模型）'

    def __init__(self, now):
        self.now, self.round = now, 0

    def ready(self):
        return None

    def discover(self, category=None, excluded=()):
        self.round += 1
        batch = f'{self.round}-{uuid4().hex[:6]}'
        topics = {
            'douyin': ['KPL 决赛名场面', '舞台镜头的小细节', '最近反复出现的口头禅', '通勤人的新梗', '比赛解说的经典一句', '网友的创意模仿', '老歌的新打开方式'],
            'xiaohongshu': ['周末微旅行', '秋季穿搭讨论', '低成本生活仪式感', '新手做饭名场面', '城市散步路线', '整理房间的小灵感'],
            'news': ['城市文化活动引发关注', '新技术走进日常生活', '大众体育赛事讨论', '公共文化空间新变化', '季节性消费话题']
        }
        rows = []
        for platform in ([category] if category else topics):
            for index, title in enumerate(topics[platform]):
                title += f'（虚构示例 {batch}）'
                url = ('https://www.douyin.com/search/' + quote(title) if platform == 'douyin' else
                       'https://www.xiaohongshu.com/search_result?' + urlencode({'keyword': title}) if platform == 'xiaohongshu' else
                       'https://www.baidu.com/s?' + urlencode({'wd': title}))
                rows.append(dict(platform=platform, title=title, event_key=f'{platform}-{batch}-{index}',
                                 content='虚构素材，只用于体验每日精选、换一条和 Excel 导出，不是真实热门事件。', url=url,
                                 published_at=(self.now() - timedelta(hours=2)).isoformat(),
                                 reason='示例筛选依据，不代表实际热度', hook=f'你注意到“{title[:20]}”里的这个细节了吗？'))
        return rows
