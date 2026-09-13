import logging
import time

from .alerts import alert_breaking
from .collector import collect_once
from .config import settings
from .trend import run_once

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("haberrss.worker")

def main():
    log.info("HaberRSS worker starting")
    while True:
        try:
            log.info("collector inserted=%s", collect_once())
        except Exception:
            log.exception("collector failed")
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
