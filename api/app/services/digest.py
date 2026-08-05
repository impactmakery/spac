"""Weekly digest: new board items on the boards each user can see."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import BoardItem, Municipality, User
from app.services.email import send_email

MAX_ITEMS = 10

COPY = {
    "he": {
        "subject": "סיכום שבועי — סוכן מחר",
        "intro": "פריטים חדשים בלוחות שלך מהשבוע האחרון:",
        "footer": "אפשר לבטל את הסיכום השבועי בעמוד ההגדרות האישיות.",
        "dir": "rtl",
    },
    "en": {
        "subject": "Weekly digest — Tomorrow Agent",
        "intro": "New items on your boards from the past week:",
        "footer": "You can turn the weekly digest off on your profile page.",
        "dir": "ltr",
    },
}


def items_for_user(db: Session, user: User, since: datetime) -> list[BoardItem]:
    scope_filter = BoardItem.scope == "global"
    if user.municipality_id:
        scope_filter = or_(
            scope_filter,
            (BoardItem.scope == "municipality")
            & (BoardItem.municipality_id == user.municipality_id),
        )
    return list(
        db.scalars(
            select(BoardItem)
            .where(BoardItem.created_at >= since, scope_filter)
            .order_by(BoardItem.created_at.desc())
            .limit(MAX_ITEMS)
        )
    )


def send_weekly_digest(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Email every opted-in active user their new board items. Skips empty digests."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=7)
    base_url = get_settings().nextauth_url

    recipients = db.scalars(
        select(User).where(
            User.status == "active",
            User.digest_enabled.is_(True),
            User.password_hash.is_not(None),
        )
    ).all()

    sent = skipped = 0
    for user in recipients:
        if user.municipality_id:
            muni = db.get(Municipality, user.municipality_id)
            if muni is not None and muni.status != "active":
                skipped += 1
                continue
        items = items_for_user(db, user, since)
        if not items:
            skipped += 1
            continue
        copy = COPY.get(user.language, COPY["he"])
        rows = "".join(
            f'<li><a href="{base_url}/{user.language}/board/{item.id}">{item.title}</a></li>'
            for item in items
        )
        html = (
            f'<div dir="{copy["dir"]}">'
            f"<p>{copy['intro']}</p><ul>{rows}</ul>"
            f"<p style='color:#666;font-size:12px'>{copy['footer']}</p></div>"
        )
        send_email(to=user.email, subject=copy["subject"], html=html)
        sent += 1
    return {"sent": sent, "skipped": skipped}
