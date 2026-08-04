"""Ingestion queue: extract → chunk → embed → chunks rows, with retries.

Queue = ingestion_jobs table claimed via FOR UPDATE SKIP LOCKED (no broker).
Deleting a source must delete its chunks in the same transaction — that
happens in the routers; this module only rebuilds chunks for live sources.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models import Chunk, IngestionJob, KbDocument
from app.rag.chunking import chunk_text
from app.rag.embeddings import get_embedding_provider
from app.rag.extract import extract_text
from app.services.storage import get_storage

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 30


def enqueue(
    db: Session,
    *,
    source_type: str,
    source_id: uuid.UUID,
    visibility: str,
    storage_key: str,
    ext: str,
    municipality_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
) -> IngestionJob:
    """Queue (re)indexing of a source. Caller owns the transaction."""
    job = IngestionJob(
        source_type=source_type,
        source_id=source_id,
        payload={
            "storage_key": storage_key,
            "ext": ext,
            "visibility": visibility,
            "municipality_id": str(municipality_id) if municipality_id else None,
            "department_id": str(department_id) if department_id else None,
        },
    )
    db.add(job)
    return job


def _set_source_status(
    db: Session, source_type: str, source_id: uuid.UUID, status: str, error: str | None
) -> None:
    if source_type == "kb":
        doc = db.get(KbDocument, source_id)
        if doc is not None:
            doc.status = status
            doc.error = error
    # board / department sources get their status hooks in Stage E


def _process(db: Session, job: IngestionJob) -> None:
    payload = job.payload
    content = get_storage().open(payload["storage_key"])
    txt = extract_text(content, payload["ext"])
    chunks = chunk_text(txt)
    embeddings = get_embedding_provider().embed(chunks) if chunks else []

    db.execute(
        delete(Chunk).where(
            Chunk.source_type == job.source_type, Chunk.source_id == job.source_id
        )
    )
    muni = payload.get("municipality_id")
    dept = payload.get("department_id")
    for content_piece, vector in zip(chunks, embeddings, strict=True):
        db.add(
            Chunk(
                source_type=job.source_type,
                source_id=job.source_id,
                municipality_id=uuid.UUID(muni) if muni else None,
                department_id=uuid.UUID(dept) if dept else None,
                visibility=payload["visibility"],
                content=content_piece,
                embedding=vector,
            )
        )


def run_pending_jobs(db: Session, *, limit: int = 10) -> int:
    """Claim and run due jobs. Returns the number processed."""
    claimed = db.scalars(
        select(IngestionJob)
        .where(IngestionJob.status == "queued", IngestionJob.run_after <= text("now()"))
        .order_by(IngestionJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for job in claimed:
        job.status = "running"
        _set_source_status(db, job.source_type, job.source_id, "processing", None)
    db.commit()

    for job in claimed:
        try:
            _process(db, job)
            job.status = "done"
            _set_source_status(db, job.source_type, job.source_id, "indexed", None)
            db.commit()
        except Exception as e:  # noqa: BLE001 — any failure retries then marks terminal
            db.rollback()
            reloaded = db.get(IngestionJob, job.id)
            if reloaded is None:
                continue
            job = reloaded
            job.attempts += 1
            job.last_error = str(e)[:2000]
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "failed"
                _set_source_status(
                    db, job.source_type, job.source_id, "not_indexable", job.last_error
                )
                log.error("ingestion terminal failure job=%s: %s", job.id, e)
            else:
                job.status = "queued"
                backoff = BACKOFF_BASE_SECONDS * (2**job.attempts)
                job.run_after = datetime.now(UTC) + timedelta(seconds=backoff)
                log.warning("ingestion retry %s/3 job=%s: %s", job.attempts, job.id, e)
            db.commit()
    return len(claimed)
