"""What is currently broken, for a system admin.

Three sources, because "an error" means three different things here and an
administrator has to act differently on each:

  - a server error, which is a defect and wants a developer
  - a document that would not index, which is usually the file and wants
    somebody to re-save or re-upload it
  - a scheduled job that failed, which usually means the digest did not go out

They are separate lists rather than one merged stream: merging them would put
things with different owners and different remedies under one heading.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_system_admin
from app.models import (
    CronRun,
    Department,
    DepartmentFile,
    IngestionJob,
    KbDocument,
    Municipality,
    User,
)
from app.services.error_log import recent_errors

router = APIRouter(prefix="/api/system/errors", tags=["system"])

LIMIT = 100


class ServerErrorOut(BaseModel):
    id: int
    occurred_at: datetime
    method: str
    path: str
    error_type: str
    message: str
    traceback: str | None
    user_email: str | None


class FailedDocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    library: str
    error: str | None
    attempts: int
    updated_at: datetime


class FailedJobOut(BaseModel):
    job: str
    period_key: str
    started_at: datetime
    error: str | None


class SystemErrorsOut(BaseModel):
    server_errors: list[ServerErrorOut]
    failed_documents: list[FailedDocumentOut]
    failed_jobs: list[FailedJobOut]


@router.get("", response_model=SystemErrorsOut)
def list_errors(
    actor: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> SystemErrorsOut:
    del actor  # the dependency is the check

    server = []
    for row in recent_errors(db, LIMIT):
        user = db.get(User, row.user_id) if row.user_id else None
        server.append(
            ServerErrorOut(
                id=row.id,
                occurred_at=row.occurred_at,
                method=row.method,
                path=row.path,
                error_type=row.error_type,
                message=row.message,
                traceback=row.traceback,
                user_email=user.email if user else None,
            )
        )

    documents = []
    stuck = db.scalars(
        select(KbDocument)
        .where(KbDocument.status == "not_indexable")
        .order_by(KbDocument.updated_at.desc())
        .limit(LIMIT)
    )
    for doc in stuck:
        muni = db.get(Municipality, doc.municipality_id) if doc.municipality_id else None
        attempts = (
            db.scalar(
                select(IngestionJob.attempts).where(
                    IngestionJob.source_type == "kb", IngestionJob.source_id == doc.id
                )
            )
            or 0
        )
        documents.append(
            FailedDocumentOut(
                id=str(doc.id),
                title=doc.title,
                filename=doc.filename,
                library=muni.name if muni else "",
                error=doc.error,
                attempts=attempts,
                updated_at=doc.updated_at,
            )
        )

    # Department files fail the same way and are just as invisible.
    dept_stuck = db.scalars(
        select(DepartmentFile)
        .where(DepartmentFile.status == "not_indexable")
        .order_by(DepartmentFile.created_at.desc())
        .limit(LIMIT)
    )
    for f in dept_stuck:
        dept = db.get(Department, f.department_id)
        muni = (
            db.get(Municipality, dept.municipality_id)
            if dept and dept.municipality_id
            else None
        )
        documents.append(
            FailedDocumentOut(
                id=str(f.id),
                title=f.filename,
                filename=f.filename,
                # Where to go looking: a department file lives in one place.
                library=" · ".join(
                    p for p in (muni.name if muni else "", dept.name if dept else "") if p
                ),
                error=f.error,
                attempts=db.scalar(
                    select(IngestionJob.attempts).where(
                        IngestionJob.source_type == "department",
                        IngestionJob.source_id == f.id,
                    )
                )
                or 0,
                updated_at=f.created_at,
            )
        )

    jobs = [
        FailedJobOut(
            job=r.job,
            period_key=r.period_key,
            started_at=r.started_at,
            error=r.error,
        )
        for r in db.scalars(
            select(CronRun)
            .where(CronRun.error.is_not(None))
            .order_by(CronRun.started_at.desc())
            .limit(LIMIT)
        )
    ]

    return SystemErrorsOut(
        server_errors=server, failed_documents=documents, failed_jobs=jobs
    )


class RetryOut(BaseModel):
    requeued: int


def _drop_jobs(db: Session, source_type: str, source_id: uuid.UUID) -> None:
    for job in db.scalars(
        select(IngestionJob).where(
            IngestionJob.source_type == source_type, IngestionJob.source_id == source_id
        )
    ):
        db.delete(job)


def _ext_of(filename: str) -> str | None:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else None


@router.post("/documents/{doc_id}/retry", response_model=RetryOut)
def retry_document(
    doc_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> RetryOut:
    """Put a failed document back in the queue.

    An errors page that can only be read is a page nobody opens twice. Most
    indexing failures are transient — a provider was rate-limited, a worker was
    replaced mid-job — and the fix is to try again.

    Both kinds of document appear in the list, so both have to be retryable
    here. A department file that only got a cheerful toast and no new job would
    be worse than no button at all.
    """
    del actor
    from app.services.ingestion import enqueue

    doc = db.get(KbDocument, doc_id)
    if doc is not None:
        _drop_jobs(db, "kb", doc.id)
        doc.status = "pending"
        doc.error = None
        enqueue(
            db,
            source_type="kb",
            source_id=doc.id,
            visibility=doc.scope,
            municipality_id=doc.municipality_id if doc.scope == "municipality" else None,
            storage_key=doc.storage_key,
            ext=_ext_of(doc.filename),
            title=doc.title,
        )
        db.commit()
        return RetryOut(requeued=1)

    f = db.get(DepartmentFile, doc_id)
    if f is None:
        raise HTTPException(status_code=404, detail="not_found")

    dept = db.get(Department, f.department_id)
    _drop_jobs(db, "department", f.id)
    f.status = "pending"
    f.error = None
    enqueue(
        db,
        source_type="department",
        source_id=f.id,
        visibility="department",
        storage_key=f.storage_key,
        ext=_ext_of(f.filename),
        title=f.filename,
        municipality_id=dept.municipality_id if dept else None,
        department_id=f.department_id,
    )
    db.commit()
    return RetryOut(requeued=1)
