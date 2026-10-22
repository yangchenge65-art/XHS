import os

from hotdesk.web import create_app
from hotdesk.scheduler import start_scheduler

app = create_app()

if __name__ == '__main__':
    stop = None
    if os.getenv('HOTDESK_SCHEDULE', '1') == '1':
        stop = start_scheduler(app.extensions['hotdesk'], app.extensions['briefing'])
    try:
        # Single-process development server: do not expose to public Internet without auth.
        app.run(host=os.getenv('HOTDESK_HOST', '127.0.0.1'), port=int(os.getenv('PORT', '8000')),
                debug=False, use_reloader=False, threaded=True)
    finally:
        if stop:
            stop.set()
