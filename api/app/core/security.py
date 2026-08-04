import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

ACCESS_TOKEN_DAYS = 30
_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def new_raw_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "muni": str(user.municipality_id) if user.municipality_id else None,
        "depts": [str(d.id) for d in user.departments],
        "tv": user.token_version,
        "lang": user.language,
        "name": user.name,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        claims = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token") from None
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.status != "active" or user.token_version != claims["tv"]:
        raise HTTPException(status_code=401, detail="session_expired")
    return user


def require_system_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "system_admin":
        raise HTTPException(status_code=404, detail="not_found")
    return user


def require_municipality_admin(user: User = Depends(get_current_user)) -> User:
    """Municipality admin or system admin."""
    if user.role not in ("municipality_admin", "system_admin"):
        raise HTTPException(status_code=404, detail="not_found")
    return user
