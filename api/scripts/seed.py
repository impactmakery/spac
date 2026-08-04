"""Minimal idempotent seed: first system admin for local development.

Usage: python scripts/seed.py [email] [password]
Defaults: root@example.org / local-dev-password-1
(The domain must pass EmailStr validation — special-use TLDs like .local are rejected.)
Full demo seed (municipalities, users, documents) arrives in Stage H.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "root@example.org"
    password = sys.argv[2] if len(sys.argv) > 2 else "local-dev-password-1"
    engine = create_engine(get_settings().database_url)
    with sessionmaker(bind=engine)() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if existing:
            print(f"already exists: {email}")
            return
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
        print(f"created system admin: {email}")


if __name__ == "__main__":
    main()
