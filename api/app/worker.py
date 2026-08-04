"""Ingestion worker: python -m app.worker. Polls the SKIP LOCKED job queue."""

import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.ingestion import run_pending_jobs

POLL_SECONDS = 2.0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("worker")
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine)
    log.info("ingestion worker started")
    while True:
        try:
            with factory() as db:
                processed = run_pending_jobs(db)
            if processed:
                log.info("processed %d job(s)", processed)
        except Exception:  # noqa: BLE001 — the worker must survive transient errors
            log.exception("worker cycle failed")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
