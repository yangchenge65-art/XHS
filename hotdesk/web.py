import io
import os
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_file

from .core import Service, Store, clock, export_excel, PLATFORMS, LABELS
from .demo import Demo
from .providers import TikHub


def create_app(data_dir=None, provider=None, now=clock):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 8192
    data = Path(data_dir or os.getenv('HOTDESK_DATA_DIR', 'data'))
    real = Service(Store(data / 'hotdesk.db'), provider or TikHub(), now)
    demo = Service(Store(data / 'demo.db'), Demo(now), now)
    app.extensions['hotdesk'] = real

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
                       schedule='每天 09:00 · 北京时间', now=now().isoformat(),
                       scheduler_enabled=os.getenv('HOTDESK_SCHEDULE', '1') == '1',
                       note='本地预留金额并非供应商账单；需正确设置每次请求的费用上界。')

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
