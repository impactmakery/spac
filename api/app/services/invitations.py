import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_token, new_raw_token
from app.models import Invitation, Municipality, User
from app.services.audit import record_audit
from app.services.notifications import send_invite_email

INVITE_TOKEN_DAYS = 7


def create_invitation(
    db: Session,
    *,
    email: str,
    role: str,
    municipality_id: uuid.UUID | None,
    department_ids: list[uuid.UUID],
    invited_by: User,
    language: str = "he",
) -> Invitation:
    """Create the invitation + shadow user and send the invite email.

    Commits the transaction. Raises 409 when the email already exists.
    """
    existing = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="email_exists")

    user = User(email=email, role=role, municipality_id=municipality_id, status="invited")
    raw = new_raw_token()
    invitation = Invitation(
        email=email,
        role=role,
        municipality_id=municipality_id,
        department_ids=[str(d) for d in department_ids],
        token_hash=hash_token(raw),
        invited_by=invited_by.id,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TOKEN_DAYS),
    )
    db.add_all([user, invitation])
    db.flush()
    record_audit(
        db,
        actor_id=invited_by.id,
        action="invitation.create",
        entity_type="invitation",
        entity_id=str(invitation.id),
        after={"email": email, "role": role,
               "municipality_id": str(municipality_id) if municipality_id else None,
               "department_ids": [str(d) for d in department_ids]},
    )
    db.commit()

    muni = db.get(Municipality, municipality_id) if municipality_id else None
    send_invite_email(
        to=email,
        inviter_name=invited_by.name,
        municipality_name=muni.name if muni else None,
        language=language,
        raw_token=raw,
    )
    return invitation


def resend_invitation(db: Session, *, invitation: Invitation, actor: User) -> None:
    """Regenerate the token + expiry and re-send the email. Commits."""
    raw = new_raw_token()
    invitation.token_hash = hash_token(raw)
    invitation.expires_at = datetime.now(UTC) + timedelta(days=INVITE_TOKEN_DAYS)
    invitation.used_at = None
    record_audit(
        db,
        actor_id=actor.id,
        action="invitation.resend",
        entity_type="invitation",
        entity_id=str(invitation.id),
    )
    db.commit()

    muni = (
        db.get(Municipality, invitation.municipality_id) if invitation.municipality_id else None
    )
    send_invite_email(
        to=invitation.email,
        inviter_name=actor.name,
        municipality_name=muni.name if muni else None,
        language="he",
        raw_token=raw,
    )
