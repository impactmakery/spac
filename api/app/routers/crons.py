"""Scheduled jobs, driven by the Railway cron service.

Every endpoint requires the CRON_SECRET bearer token, is idempotent per period
(a second call in the same period is a no-op), and records a run row.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import (
    Chunk,
    Conversation,
    CronRun,
    Department,
    DepartmentFile,
    IngestionJob,
    Message,
    MessageDebug,
    User,
)
from app.services.digest import send_weekly_digest
from app.services.error_log import prune_errors
from app.services.metrics import TZ, rollup_day
from app.services.storage import get_storage

router = APIRouter(prefix="/api/cron", tags=["cron"])

DEBUG_RETENTION_DAYS = 90
CHAT_RETENTION_DAYS = 90


def require_cron_secret(authorization: str = Header(default="")) -> None:
    secret = get_settings().cron_secret
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="unauthorized")


def _claim(db: Session, job: str, period_key: str) -> CronRun | None:
    """Insert the run row; returns None when this period already ran."""
    existing = db.scalar(
        select(CronRun).where(CronRun.job == job, CronRun.period_key == period_key)
    )
    if existing is not None:
        return None
    run = CronRun(job=job, period_key=period_key)
    db.add(run)
    db.commit()
    return run


def _finish(db: Session, run: CronRun, counts: dict) -> None:
    run.finished_at = datetime.now(UTC)
    run.counts = counts
    db.commit()


@router.post("/metrics-rollup", dependencies=[Depends(require_cron_secret)])
def metrics_rollup(day: str | None = None, db: Session = Depends(get_db)) -> dict:
    target = (
        date.fromisoformat(day)
        if day
        else (datetime.now(TZ).date() - timedelta(days=1))
    )
    run = _claim(db, "metrics-rollup", target.isoformat())
    if run is None:
        return {"skipped": "already_ran", "day": target.isoformat()}
    counts = rollup_day(db, target)
    _finish(db, run, counts)
    return {"day": target.isoformat(), **counts}


DIGEST_WEEKDAY = 1  # Monday
DIGEST_HOUR = 8  # 08:00 Asia/Jerusalem


@router.post("/weekly-digest", dependencies=[Depends(require_cron_secret)])
def weekly_digest(force: bool = False, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(TZ)
    # One shared cron service calls every job on each tick, so this endpoint
    # decides its own moment: the first tick at or after Monday 08:00 local.
    # Computing in Asia/Jerusalem keeps it correct across daylight saving.
    if not force and (
        now.isoweekday() != DIGEST_WEEKDAY or now.hour < DIGEST_HOUR
    ):
        return {"skipped": "not_due"}

    iso_year, iso_week, _ = now.isocalendar()
    run = _claim(db, "weekly-digest", f"{iso_year}-W{iso_week:02d}")
    if run is None:
        return {"skipped": "already_ran"}
    counts = send_weekly_digest(db, now=now)
    _finish(db, run, counts)
    return counts


@router.post("/archive-purge", dependencies=[Depends(require_cron_secret)])
def archive_purge(db: Session = Depends(get_db)) -> dict:
    """Permanently delete departments archived more than 90 days ago, plus the
    90-day retention sweeps for chat history, retrieval debug rows and the
    recorded server errors."""
    today = datetime.now(TZ).date()
    run = _claim(db, "archive-purge", today.isoformat())
    if run is None:
        return {"skipped": "already_ran"}

    now = datetime.now(UTC)
    storage = get_storage()

    expired = db.scalars(
        select(Department).where(
            Department.status == "archived",
            Department.archive_expires_at.is_not(None),
            Department.archive_expires_at < now,
        )
    ).all()
    purged_files = 0
    for department in expired:
        files = db.scalars(
            select(DepartmentFile).where(DepartmentFile.department_id == department.id)
        ).all()
        for file in files:
            db.execute(
                delete(Chunk).where(
                    Chunk.source_type == "department", Chunk.source_id == file.id
                )
            )
            db.execute(
                delete(IngestionJob).where(
                    IngestionJob.source_type == "department",
                    IngestionJob.source_id == file.id,
                )
            )
        purged_files += len(files)
        db.execute(delete(Chunk).where(Chunk.department_id == department.id))
        db.delete(department)  # files/posts/comments cascade
        db.commit()
        for file in files:
            storage.delete(file.storage_key)

    debug_cutoff = now - timedelta(days=DEBUG_RETENTION_DAYS)
    debug_result = db.execute(
        delete(MessageDebug).where(MessageDebug.created_at < debug_cutoff)
    )
    assert isinstance(debug_result, CursorResult)
    debug_deleted = debug_result.rowcount

    # deactivated users' chat history is retained 90 days, then purged
    chat_cutoff = now - timedelta(days=CHAT_RETENTION_DAYS)
    stale_conversations = db.scalars(
        select(Conversation.id)
        .join(User, User.id == Conversation.user_id)
        .where(User.status == "inactive", Conversation.updated_at < chat_cutoff)
    ).all()
    if stale_conversations:
        db.execute(
            delete(Message).where(Message.conversation_id.in_(stale_conversations))
        )
        db.execute(
            delete(Conversation).where(Conversation.id.in_(stale_conversations))
        )
    db.commit()

    # The errors page keeps 90 days like everything else here; a table nobody
    # trims is a table that eventually fills the disk.
    errors_purged = prune_errors(db)

    counts = {
        "departments_purged": len(expired),
        "department_files_purged": purged_files,
        "message_debug_purged": debug_deleted or 0,
        "conversations_purged": len(stale_conversations),
        "errors_purged": errors_purged,
    }
    _finish(db, run, counts)
    return counts
