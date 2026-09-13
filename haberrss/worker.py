import logging
import time

from .alerts import alert_breaking
from .collector import collect_once
from .config import settings
from .realtime import collect_early_signals
from .trend import run_once

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("haberrss.worker")


def main():
    log.info("HaberRSS worker starting")
    signal_every = max(30, min(settings.signal_interval_seconds, 300))
    last_signal = 0.0
    while True:
        try:
            log.info("collector inserted=%s", collect_once())
        except Exception:
            log.exception("collector failed")

        now = time.monotonic()
        if now - last_signal >= signal_every:
            try:
                log.info("early signals inserted=%s", collect_early_signals())
            except Exception:
                log.exception("early signal collectors failed")
            last_signal = now

        try:
            run_once()
        except Exception:
            log.exception("trend engine failed")
        try:
            log.info("alerts sent=%s", alert_breaking())
        except Exception:
            log.exception("alert dispatcher failed")
        time.sleep(max(5, min(settings.scan_interval_seconds, settings.trend_interval_seconds)))


if __name__ == "__main__":
    main()
