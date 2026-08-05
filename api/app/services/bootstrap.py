"""Create the first system administrator on a brand-new deployment.

Runs only when the users table is completely empty, so it cannot overwrite or
re-create an account later: once anyone exists, this is a no-op forever.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import User

log = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 10


def bootstrap_first_admin(db: Session) -> bool:
    """Returns True when an administrator was created."""
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip()
    password = settings.bootstrap_admin_password

    if not email or not password:
        return False
    if len(password) < MIN_PASSWORD_LENGTH:
        log.warning(
            "BOOTSTRAP_ADMIN_PASSWORD is shorter than %d characters — skipping",
            MIN_PASSWORD_LENGTH,
        )
        return False

    if db.scalar(select(func.count(User.id))):
        return False  # the platform already has users

    db.add(
        User(
            email=email,
            password_hash=hash_password(password),
            name="System Admin",
            role="system_admin",
            status="active",
            language="he",
        )
    )
    db.commit()
    log.info("bootstrapped first system administrator: %s", email)
    return True
