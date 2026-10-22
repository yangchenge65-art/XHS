import logging
import threading

from .core import PLATFORMS, TZ


def tick(service, briefing=None):
    now = service.now().astimezone(TZ)
    if now.hour < 9:
        return
    if briefing is not None:
        if briefing.load() is None:
            briefing.generate()
        return
    runs = service.store.runs(now)
    # One automatic attempt per platform/day, including failures. Manual retry is explicit.
    if any(platform not in runs for platform in PLATFORMS):
        service.collect()


def start_scheduler(service, briefing=None):
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                tick(service, briefing)
            except Exception:
                # Do not log response bodies/URLs, which may contain supplier credentials.
                logging.error('定时采集发生内部错误，请检查配置并手动重试')
            stop.wait(60)

    thread = threading.Thread(target=loop, name='hotdesk-daily', daemon=True)
    thread.start()
    return stop
