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

from app.models import BoardItem, Chunk, DepartmentFile, IngestionJob, KbDocument
from app.rag.chunking import chunk_text
from app.rag.embeddings import get_embedding_provider
from app.rag.extract import extract_text
from app.rag.graph import index_chunk
from app.services.storage import get_storage
from app.services.uploads import is_extractable

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 30

# How long a claimed job may sit in 'running' before it is assumed abandoned.
#
# A worker that is killed mid-batch — out of memory on a large scan, a deploy,
# a container restart — leaves its claims behind, and the claim query only ever
# looks at 'queued'. Without this those jobs are stranded permanently: the
# document shows "processing" forever and nothing retries it.
#
# Generous on purpose. A batch is marked 'running' when it is claimed, so the
# last job in a batch of ten has already been sitting in that state while the
# other nine were OCR'd. The lease has to outlast a whole slow batch or a
# healthy worker would have its own work taken away mid-run.
LEASE_SECONDS = 2 * 60 * 60


def enqueue(
    db: Session,
    *,
    source_type: str,
    source_id: uuid.UUID,
    visibility: str,
    storage_key: str | None = None,
    ext: str | None = None,
    text_content: str | None = None,
    title: str | None = None,
    municipality_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
) -> IngestionJob:
    """Queue (re)indexing of a source. Caller owns the transaction.

    Pass storage_key+ext for files, or text_content for text-only sources
    (board descriptions of link items, department posts). The title, when the
    source has one, is prepended to every chunk so a passage retrieved from the
    middle of a document still says what document it came from.
    """
    job = IngestionJob(
        source_type=source_type,
        source_id=source_id,
        payload={
            "storage_key": storage_key,
            "ext": ext,
            "text": text_content,
            "title": title,
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
    elif source_type == "board":
        item = db.get(BoardItem, source_id)
        if item is not None:
            item.indexing_status = status
    elif source_type == "department":
        # only files carry a status; posts share the source_type but no row here
        file = db.get(DepartmentFile, source_id)
        if file is not None:
            file.status = status
            file.error = error


def _process(db: Session, job: IngestionJob) -> None:
    payload = job.payload
    if payload.get("storage_key"):
        content = get_storage().open(payload["storage_key"])
        if is_extractable(payload.get("ext")):
            txt = extract_text(content, payload["ext"])
        else:
            # Any file type may be uploaded, and most of them hold no text we can
            # read. That is not a failure: the post keeps its title and
            # description, and the file is still there to download. Marking it
            # 'not indexable' would be technically true and practically useless.
            log.info(
                "no text extractor for .%s; indexing title and description only",
                payload.get("ext"),
            )
            txt = ""
        if payload.get("text"):
            txt = payload["text"] + "\n\n" + txt if txt else payload["text"]
    else:
        txt = payload.get("text") or ""
    chunks = chunk_text(txt, title=payload.get("title"))
    embeddings = get_embedding_provider().embed(chunks) if chunks else []

    db.execute(
        delete(Chunk).where(
            Chunk.source_type == job.source_type, Chunk.source_id == job.source_id
        )
    )
    muni = payload.get("municipality_id")
    dept = payload.get("department_id")
    municipality_id = uuid.UUID(muni) if muni else None
    department_id = uuid.UUID(dept) if dept else None
    for content_piece, vector in zip(chunks, embeddings, strict=True):
        chunk = Chunk(
            source_type=job.source_type,
            source_id=job.source_id,
            municipality_id=municipality_id,
            department_id=department_id,
            visibility=payload["visibility"],
            content=content_piece,
            embedding=vector,
        )
        db.add(chunk)
        db.flush()  # the graph rows reference chunk.id
        try:
            index_chunk(
                db,
                chunk_id=chunk.id,
                content=content_piece,
                visibility=payload["visibility"],
                municipality_id=municipality_id,
                department_id=department_id,
            )
        except Exception as e:  # noqa: BLE001
            # The graph is an enhancement over search that already works. A bad
            # extraction must not cost the document its embedding, so it is
            # logged and the chunk is indexed without graph edges.
            log.warning("graph indexing failed for chunk %s: %s", chunk.id, e)


def reclaim_stalled_jobs(db: Session) -> int:
    """Return jobs abandoned by a dead worker to the queue. Returns how many.

    Counts an attempt rather than requeueing freely: a document that reliably
    kills the worker would otherwise cycle forever, taking the queue down with
    it every time. After MAX_ATTEMPTS it becomes a visible failure instead.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=LEASE_SECONDS)
    stalled = db.scalars(
        select(IngestionJob)
        .where(IngestionJob.status == "running", IngestionJob.updated_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    for job in stalled:
        job.attempts += 1
        job.last_error = "worker stopped while this job was running"
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            _set_source_status(
                db, job.source_type, job.source_id, "not_indexable", job.last_error
            )
            log.error("ingestion job %s abandoned too often; giving up", job.id)
        else:
            job.status = "queued"
            job.run_after = datetime.now(UTC)
            _set_source_status(db, job.source_type, job.source_id, "pending", None)
            log.warning("requeued stalled ingestion job %s", job.id)
    if stalled:
        db.commit()
    return len(stalled)


def run_pending_jobs(db: Session, *, limit: int = 10) -> int:
    """Claim and run due jobs. Returns the number processed."""
    reclaim_stalled_jobs(db)
    claimed = db.scalars(
        select(IngestionJob)
        .where(
            IngestionJob.status == "queued",
            # clock_timestamp(), not now(): now() is the transaction start time, so a
            # session that began before a job was enqueued would never claim it.
            IngestionJob.run_after <= text("clock_timestamp()"),
        )
        .order_by(IngestionJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    for job in claimed:
        job.status = "running"
        _set_source_status(db, job.source_type, job.source_id, "processing", None)
    db.commit()

    for job in claimed:
        # Read the identifiers up front: deleting a document removes its job
        # rows, and after a rollback even reading job.id would try to reload a
        # row that is gone (ObjectDeletedError) and kill the worker cycle.
        job_id, source_type, source_id = job.id, job.source_type, job.source_id
        # Restart this job's lease as its turn begins, so the clock measures how
        # long this job has been worked on rather than how long the batch has.
        job.updated_at = datetime.now(UTC)
        db.commit()
        try:
            _process(db, job)
            job.status = "done"
            _set_source_status(db, source_type, source_id, "indexed", None)
            db.commit()
        except Exception as e:  # noqa: BLE001 — any failure retries then marks terminal
            db.rollback()
            reloaded = db.get(IngestionJob, job_id)
            if reloaded is None:
                # the source was deleted while we were indexing it — nothing to retry
                log.info("ingestion job %s vanished mid-run; skipping", job_id)
                continue
            reloaded.attempts += 1
            reloaded.last_error = str(e)[:2000]
            if reloaded.attempts >= MAX_ATTEMPTS:
                reloaded.status = "failed"
                _set_source_status(
                    db, source_type, source_id, "not_indexable", reloaded.last_error
                )
                log.error("ingestion terminal failure job=%s: %s", job_id, e)
            else:
                reloaded.status = "queued"
                backoff = BACKOFF_BASE_SECONDS * (2**reloaded.attempts)
                reloaded.run_after = datetime.now(UTC) + timedelta(seconds=backoff)
                log.warning(
                    "ingestion retry %s/3 job=%s: %s", reloaded.attempts, job_id, e
                )
            db.commit()
    return len(claimed)
