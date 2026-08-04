import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import forgot_limiter, login_limiter
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_token,
    new_raw_token,
    verify_password,
)
from app.models import Department, Invitation, Municipality, PasswordResetToken, User
from app.schemas.auth import (
    AcceptInviteIn,
    ChangePasswordIn,
    ForgotIn,
    InviteInfoOut,
    LoginIn,
    LoginOut,
    ResetIn,
    TokenOut,
    UserOut,
)
from app.services.notifications import send_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

RESET_TOKEN_HOURS = 1


def user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        municipality_id=str(user.municipality_id) if user.municipality_id else None,
        department_ids=[str(d.id) for d in user.departments],
        language=user.language,
        digest_enabled=user.digest_enabled,
    )


def _find_active_user(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(func.lower(User.email) == email.lower(), User.status == "active")
    )


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    ip = request.client.host if request.client else "unknown"
    if not login_limiter.hit(ip):
        raise HTTPException(status_code=429, detail="too_many_attempts")
    user = _find_active_user(db, body.email)
    if user is None or not user.password_hash or not verify_password(
        body.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if user.municipality is not None and user.municipality.status != "active":
        raise HTTPException(status_code=401, detail="invalid_credentials")
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return LoginOut(access_token=create_access_token(user), user=user_out(user))


@router.post("/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    if not forgot_limiter.hit(ip):
        raise HTTPException(status_code=429, detail="too_many_attempts")
    user = _find_active_user(db, body.email)
    if user is not None:
        raw = new_raw_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=RESET_TOKEN_HOURS),
            )
        )
        db.commit()
        send_reset_email(to=user.email, name=user.name, language=user.language, raw_token=raw)
    return {"ok": True}


@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)) -> dict:
    token = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token))
    )
    if token is None:
        raise HTTPException(status_code=404, detail="invalid_token")
    if token.used_at is not None or token.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="token_expired")
    user = db.get(User, token.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=410, detail="token_expired")
    user.password_hash = hash_password(body.password)
    user.token_version += 1
    token.used_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}


def _load_invitation(db: Session, raw_token: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(raw_token)))
    if inv is None:
        raise HTTPException(status_code=404, detail="invalid_token")
    if inv.used_at is not None or inv.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="invitation_expired")
    return inv


@router.get("/invite-info", response_model=InviteInfoOut)
def invite_info(token: str, db: Session = Depends(get_db)) -> InviteInfoOut:
    inv = _load_invitation(db, token)
    inviter = db.get(User, inv.invited_by) if inv.invited_by else None
    muni = db.get(Municipality, inv.municipality_id) if inv.municipality_id else None
    dept_names = [
        d.name
        for d in db.scalars(
            select(Department).where(
                Department.id.in_([uuid.UUID(i) for i in inv.department_ids])
            )
        )
    ] if inv.department_ids else []
    return InviteInfoOut(
        email=inv.email,
        inviter_name=inviter.name if inviter else None,
        municipality_name=muni.name if muni else None,
        department_names=dept_names,
        role=inv.role,
    )


@router.post("/accept-invite", response_model=LoginOut)
def accept_invite(body: AcceptInviteIn, db: Session = Depends(get_db)) -> LoginOut:
    inv = _load_invitation(db, body.token)
    user = db.scalar(
        select(User).where(func.lower(User.email) == inv.email.lower(), User.status == "invited")
    )
    if user is None:
        raise HTTPException(status_code=410, detail="invitation_expired")
    user.name = body.name
    user.password_hash = hash_password(body.password)
    user.language = body.language
    user.status = "active"
    user.last_login_at = datetime.now(UTC)
    if inv.department_ids:
        user.departments = list(
            db.scalars(
                select(Department).where(
                    Department.id.in_([uuid.UUID(i) for i in inv.department_ids])
                )
            )
        )
    inv.used_at = datetime.now(UTC)
    db.commit()
    return LoginOut(access_token=create_access_token(user), user=user_out(user))


@router.post("/change-password", response_model=TokenOut)
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not user.password_hash or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="wrong_password")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    return TokenOut(access_token=create_access_token(user))
