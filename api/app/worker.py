"""Ingestion worker: python -m app.worker. Polls the SKIP LOCKED job queue."""

import logging
import signal
import time
from types import FrameType

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.ingestion import run_pending_jobs

POLL_SECONDS = 2.0

_stopping = False


def _request_stop(signum: int, _frame: FrameType | None) -> None:
    """Finish the job in hand, hand back the rest, then exit.

    Railway sends SIGTERM before replacing a container, which happens on every
    deploy. Dying on the spot leaves a whole claimed batch to sit out the lease
    before anything picks it up again.
    """
    global _stopping
    _stopping = True
    logging.getLogger("worker").info("signal %s received; finishing current job", signum)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("worker")
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine)
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    log.info("ingestion worker started")
    while not _stopping:
        try:
            with factory() as db:
                processed = run_pending_jobs(db, should_stop=lambda: _stopping)
            if processed:
                log.info("processed %d job(s)", processed)
        except Exception:  # noqa: BLE001 — the worker must survive transient errors
            log.exception("worker cycle failed")
        if _stopping:
            break
        time.sleep(POLL_SECONDS)
    log.info("ingestion worker stopped")


if __name__ == "__main__":
    main()
