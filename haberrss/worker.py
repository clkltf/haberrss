import logging, time
from .alerts import alert_breaking
from .collector import collect_once
from .realtime import collect_early_signals
from .trend import run_once
from .runtime import current

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log=logging.getLogger("haberrss.worker")

def main():
    log.info("HaberRSS worker starting")
    last_signal=0.0
    while True:
        cfg=current()
        logging.getLogger().setLevel(getattr(logging,cfg.log_level.upper(),logging.INFO))
        try: log.info("collector inserted=%s",collect_once())
        except Exception: log.exception("collector failed")
        now=time.monotonic()
        if now-last_signal>=cfg.signal_interval_seconds:
            try: log.info("early signals inserted=%s",collect_early_signals())
            except Exception: log.exception("early signal collectors failed")
            last_signal=now
        try: run_once()
        except Exception: log.exception("trend engine failed")
        try: log.info("alerts sent=%s",alert_breaking())
        except Exception: log.exception("alert dispatcher failed")
        time.sleep(max(5,min(cfg.scan_interval_seconds,cfg.trend_interval_seconds)))

if __name__=='__main__': main()
