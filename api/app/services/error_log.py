"""Record unhandled server errors so they outlive the container.

Railway keeps container logs for seven days and only a system admin can read
them. A municipality reporting on Monday that "it broke last week" was, until
this, unanswerable.
"""

import logging
import traceback
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ErrorLog

log = logging.getLogger(__name__)

# Enough to identify the failure without storing a novel per row.
MAX_MESSAGE = 2_000
MAX_TRACEBACK = 8_000

# Kept long enough to investigate a report from a fortnight ago, short enough
# that the table never becomes a thing to manage.
RETENTION_DAYS = 90


def record_error(
    db: Session,
    *,
    method: str,
    path: str,
    status_code: int,
    exc: BaseException,
    user_id: uuid.UUID | None = None,
) -> None:
    """Write one error row. Never raises.

    This runs while a request is already failing. If recording the failure
    fails too, the caller must still get its 500 — so everything here is inside
    one try, and the fallback is the log line we always had.
    """
    try:
        db.add(
            ErrorLog(
                method=method,
                # The path only. Query strings carry search terms and ids, and
                # this table is read by a system admin looking at every
                # municipality's errors at once.
                path=path,
                status_code=status_code,
                error_type=type(exc).__name__,
                message=str(exc)[:MAX_MESSAGE] or type(exc).__name__,
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )[-MAX_TRACEBACK:],
                user_id=user_id,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — a failure to record must not mask the failure
        log.exception("could not record an error to error_log")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass


def recent_errors(db: Session, limit: int = 100) -> list[ErrorLog]:
    return list(
        db.scalars(select(ErrorLog).order_by(ErrorLog.occurred_at.desc()).limit(limit))
    )


def prune_errors(db: Session, *, now: datetime | None = None) -> int:
    """Drop anything past the retention window. Returns how many went."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    stale = list(db.scalars(select(ErrorLog.id).where(ErrorLog.occurred_at < cutoff)))
    if stale:
        db.execute(delete(ErrorLog).where(ErrorLog.id.in_(stale)))
        db.commit()
    return len(stale)
