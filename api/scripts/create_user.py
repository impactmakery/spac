"""Create a user with a password directly, bypassing the invitation email.

The normal path is an invitation: an admin invites, Resend delivers a link, the
invitee sets their own password. That path needs email working, and the
invitation token is stored hashed — so with no RESEND_API_KEY configured an
invitation can be created but never accepted, and the link cannot be recovered
from the database. This script is the way in until email is configured, and the
way to make the very first accounts on a fresh environment.

Usage:
    python scripts/create_user.py EMAIL PASSWORD --role system_admin
    python scripts/create_user.py EMAIL PASSWORD --role municipality_admin \\
        --municipality "עיריית נהריה" --create
    python scripts/create_user.py EMAIL PASSWORD --role department_user \\
        --municipality "עיריית נהריה" --department "רווחה" --department "חינוך" --create

On Railway:
    railway run --service api python scripts/create_user.py ...

Refuses to touch an existing account unless --reset-password is given, so it
cannot silently take over a real user's login.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Department, Municipality, User  # noqa: E402

MIN_PASSWORD = 10  # matches the API's own policy


def _resolve_municipality(db: Session, name: str, create: bool) -> Municipality:
    muni = db.scalar(select(Municipality).where(Municipality.name == name))
    if muni is None:
        if not create:
            existing = [m.name for m in db.scalars(select(Municipality))]
            raise SystemExit(
                f"no municipality named {name!r}. Pass --create to add it, or use "
                f"one of: {existing or 'none exist yet'}"
            )
        muni = Municipality(name=name)
        db.add(muni)
        db.flush()
        print(f"created municipality: {name}")
    return muni


def _resolve_departments(
    db: Session, muni: Municipality, names: list[str], create: bool
) -> list[Department]:
    out = []
    for name in names:
        dept = db.scalar(
            select(Department).where(
                Department.municipality_id == muni.id, Department.name == name
            )
        )
        if dept is None:
            if not create:
                existing = [
                    d.name
                    for d in db.scalars(
                        select(Department).where(Department.municipality_id == muni.id)
                    )
                ]
                raise SystemExit(
                    f"no department named {name!r} in {muni.name}. Pass --create to "
                    f"add it, or use one of: {existing or 'none exist yet'}"
                )
            dept = Department(municipality_id=muni.id, name=name)
            db.add(dept)
            db.flush()
            print(f"created department: {muni.name} / {name}")
        out.append(dept)
    return out


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: str,
    name: str | None,
    municipality_name: str | None,
    department_names: list[str],
    language: str,
    create_missing: bool,
    reset_password: bool,
    digest_enabled: bool = True,
) -> User:
    if len(password) < MIN_PASSWORD:
        raise SystemExit(f"password must be at least {MIN_PASSWORD} characters")

    # Role and scope have to agree, or the account is unusable in ways that only
    # show up as confusing 404s later.
    if role == "system_admin" and municipality_name:
        raise SystemExit("a system admin belongs to no municipality — drop --municipality")
    if role != "system_admin" and not municipality_name:
        raise SystemExit(f"--municipality is required for role {role}")
    if role == "system_admin" and department_names:
        raise SystemExit("a system admin belongs to no department — drop --department")

    existing = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if existing and not reset_password:
        raise SystemExit(
            f"{email} already exists (role {existing.role}). Pass --reset-password to "
            "set a new password on it."
        )

    muni = (
        _resolve_municipality(db, municipality_name, create_missing)
        if municipality_name
        else None
    )
    departments = (
        _resolve_departments(db, muni, department_names, create_missing)
        if muni and department_names
        else []
    )

    if existing:
        existing.password_hash = hash_password(password)
        existing.token_version += 1  # invalidate any session using the old password
        db.commit()
        print(f"reset the password for {email} (role {existing.role})")
        return existing

    user = User(
        email=email,
        name=name,
        role=role,
        status="active",
        language=language,
        password_hash=hash_password(password),
        municipality_id=muni.id if muni else None,
        digest_enabled=digest_enabled,
    )
    db.add(user)
    db.flush()
    for dept in departments:
        user.departments.append(dept)
    db.commit()

    scope = muni.name if muni else "all municipalities"
    if departments:
        scope += " / " + ", ".join(d.name for d in departments)
    print(f"created {role}: {email}  ({scope})")

    if role == "department_user" and not departments:
        print(
            "  warning: this user belongs to no department, so they will see no "
            "department content and the assistant will answer only from global and "
            "municipality material"
        )
    return user


def main() -> None:
    # The examples below are Hebrew and the Windows console defaults to a
    # codepage that cannot encode them — --help must not be what crashes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument(
        "--role", required=True,
        choices=["system_admin", "municipality_admin", "department_user"],
    )
    parser.add_argument("--name", help="display name")
    parser.add_argument("--municipality", help="municipality name (exact)")
    parser.add_argument(
        "--department", action="append", default=[],
        help="department name; repeat for several",
    )
    parser.add_argument("--language", choices=["he", "en"], default="he")
    parser.add_argument(
        "--create", action="store_true",
        help="create the municipality/departments if they do not exist yet",
    )
    parser.add_argument(
        "--no-digest", action="store_true",
        help=(
            "do not send this account the weekly digest — for placeholder "
            "addresses that would only bounce"
        ),
    )
    parser.add_argument(
        "--reset-password", action="store_true",
        help="allow overwriting the password of an existing account",
    )
    args = parser.parse_args()

    engine = create_engine(get_settings().database_url)
    with sessionmaker(bind=engine)() as db:
        create_user(
            db,
            email=args.email,
            password=args.password,
            role=args.role,
            name=args.name,
            municipality_name=args.municipality,
            digest_enabled=not args.no_digest,
            department_names=args.department,
            language=args.language,
            create_missing=args.create,
            reset_password=args.reset_password,
        )


if __name__ == "__main__":
    main()
