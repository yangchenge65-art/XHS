import io
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_file

from .core import Service, Store, clock, export_excel, PLATFORMS, LABELS
from .demo import Demo, DemoResearch
from .providers import TikHub
from .briefs import Briefing
from .settings import Settings
from .openai_research import OpenAIResearch
from .codex_research import CodexResearch, RoutingResearch


def create_app(data_dir=None, provider=None, now=clock, researcher=None, settings=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 8192
    data = Path(data_dir or os.getenv('HOTDESK_DATA_DIR', 'data'))
    real = Service(Store(data / 'hotdesk.db'), provider or TikHub(), now)
    demo = Service(Store(data / 'demo.db'), Demo(now), now)
    settings = settings or Settings(data)
    codex = CodexResearch(settings, real.store, data, now)
    research = researcher or RoutingResearch(settings, codex, OpenAIResearch(settings, real.store, now))
    briefing = Briefing(real.store, research, data, now)
    demo_briefing = Briefing(demo.store, DemoResearch(now), data, now, demo=True)
    app.extensions['hotdesk'] = real
    app.extensions['briefing'] = briefing

    @app.before_request
    def check_origin():
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and urlsplit(origin).netloc != request.host:
                return jsonify(error='不接受跨站操作'), 403
            if not request.is_json:
                return jsonify(error='请求必须使用 JSON'), 415

    def selected():
        return demo if request.args.get('demo') == '1' else real

    def marked(result):
        result['demo'] = selected() is demo
        if result['demo']:
            result['coverage'] = '虚构示例数据，仅用于体验。链接为平台搜索入口，不是事件原始链接。'
        return result

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/status')
    def status():
        source = real.provider
        sources = {p: dict(name=LABELS[p], hot=source.ready(p, 'hot'), search=source.ready(p, 'search')) for p in PLATFORMS}
        return jsonify(budget=30, reserved=real.store.spent(now()), sources=sources,
                       openai=settings.public(), research_error=research.ready(), codex_calls=codex.usage(),
                       engine_label=getattr(research, 'engine_name', '当前模型'),
                       schedule='每天 09:00 · 北京时间', now=now().isoformat(),
                       scheduler_enabled=os.getenv('HOTDESK_SCHEDULE', '1') == '1',
                       note='本地预留金额并非供应商账单；需正确设置每次请求的费用上界。')

    def selected_brief():
        return demo_briefing if request.args.get('demo') == '1' else briefing

    @app.get('/api/brief')
    def get_brief():
        if selected_brief() is demo_briefing:
            demo_briefing.generate()
        return jsonify(selected_brief().report())

    @app.post('/api/brief/generate')
    def generate_brief():
        return jsonify(selected_brief().generate())

    @app.post('/api/brief/replace')
    def replace_brief():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('slot'), str) or not isinstance(body.get('expected_id'), str):
            return jsonify(error='请选择需要替换的素材'), 400
        try:
            return jsonify(selected_brief().replace(body['slot'], body['expected_id']))
        except ValueError as exc:
            return jsonify(error=str(exc)), 409

    @app.get('/api/brief/export')
    def export_brief():
        if not selected_brief().report()['items']:
            return jsonify(error='请先生成今日精选；读取和导出不会触发付费请求'), 409
        return send_file(io.BytesIO(selected_brief().excel()),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         download_name=f'hotdesk-{now():%Y%m%d}-daily-nine{"-demo" if selected_brief().demo else ""}.xlsx', as_attachment=True)

    @app.post('/api/settings/openai')
    def save_openai():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('api_key', ''), str) or (body.get('cost') is not None and not isinstance(body['cost'], (str, int, float))):
            return jsonify(error='请输入正确的账户配置'), 400
        try:
            return jsonify(settings.save(api_key=body.get('api_key'), cost=body.get('cost'), clear=body.get('clear') is True, engine=body.get('engine')))
        except (ValueError, OSError) as exc:
            # Only controlled validation messages are surfaced, never OS file paths/contents.
            message = str(exc) if isinstance(exc, ValueError) else '无法保存账户配置，请检查数据目录权限'
            return jsonify(error=message), 400

    @app.post('/api/openai/check')
    @app.post('/api/research/check')
    def check_openai():
        from .core import SourceError
        try:
            return jsonify(research.check_connection())
        except SourceError as exc:
            return jsonify(error=str(exc)), 400

    @app.post('/api/codex/connect')
    def connect_codex():
        if os.name != 'nt':
            return jsonify(error='请在你的 Windows 电脑上双击 Connect-Codex.bat；云环境不能替你登录本机账户'), 400
        script = Path(__file__).resolve().parents[1] / 'windows' / 'Connect-Codex.ps1'
        try:
            subprocess.Popen(['powershell.exe', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError:
            return jsonify(error='无法打开登录窗口，请直接双击 Connect-Codex.bat'), 400
        return jsonify(ok=True, message='已打开安装和登录窗口，请在官方页面完成 ChatGPT 登录，然后刷新状态。')

    @app.get('/api/report')
    def report():
        if selected() is demo:
            demo.collect()
        return jsonify(marked(selected().report()))

    @app.post('/api/collect')
    def collect():
        return jsonify(marked(selected().collect()))

    @app.post('/api/search')
    def search():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('keyword'), str):
            return jsonify(error='请输入关键词'), 400
        try:
            result = selected().search(body['keyword'])
            selected().store.cache_set('export:' + body['keyword'].strip().casefold(), now(), result)
            return jsonify(marked(result))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.get('/api/export')
    def export():
        keyword = request.args.get('keyword', '').strip()
        if keyword:
            # Exports never trigger paid calls; a successful search must exist first.
            result = selected().store.cache_get('export:' + keyword.casefold(), now())
            if result is None:
                return jsonify(error='请先完成查询；查询缓存过期后需要重新查询再导出'), 409
            result = Service.filter_window(result, now())
        else:
            if selected() is demo:
                demo.collect()
            result = selected().report()
        result = marked(result)
        return send_file(io.BytesIO(export_excel(result, demo=result['demo'])),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         download_name=f'hotdesk-{now():%Y%m%d}-{"demo" if result["demo"] else "report"}.xlsx', as_attachment=True)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
        return response

    return app
