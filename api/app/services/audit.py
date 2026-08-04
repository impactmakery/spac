"""Append-only audit trail for admin mutations. Never update or delete rows."""

import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Add an audit row to the caller's transaction (no commit here)."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
