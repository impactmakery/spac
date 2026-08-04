import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_municipality_admin, require_system_admin
from app.models import Department, Invitation, Municipality, User
from app.services.audit import record_audit

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


class DepartmentRef(BaseModel):
    id: str
    name: str


class AdminUserOut(BaseModel):
    id: str
    name: str | None
    email: str
    role: str
    status: str
    municipality_id: str | None
    municipality_name: str | None
    departments: list[DepartmentRef]
    last_login_at: datetime | None
    has_zero_departments: bool
    invitation_id: str | None


class DepartmentsPut(BaseModel):
    department_ids: list[str]


def _scoped_user_or_404(db: Session, actor: User, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="not_found")
    if actor.role == "municipality_admin" and user.municipality_id != actor.municipality_id:
        raise HTTPException(status_code=404, detail="not_found")
    return user


def _out(db: Session, user: User) -> AdminUserOut:
    invitation_id = None
    if user.status == "invited":
        inv = db.scalar(
            select(Invitation)
            .where(
                func.lower(Invitation.email) == user.email.lower(),
                Invitation.used_at.is_(None),
            )
            .order_by(Invitation.created_at.desc())
        )
        invitation_id = str(inv.id) if inv else None
    muni = db.get(Municipality, user.municipality_id) if user.municipality_id else None
    departments = [
        DepartmentRef(id=str(d.id), name=d.name)
        for d in user.departments
        if d.status == "active"
    ]
    return AdminUserOut(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
        municipality_id=str(user.municipality_id) if user.municipality_id else None,
        municipality_name=muni.name if muni else None,
        departments=departments,
        last_login_at=user.last_login_at,
        has_zero_departments=(user.role == "department_user" and not departments),
        invitation_id=invitation_id,
    )


@router.get("", response_model=list[AdminUserOut])
def list_users(
    search: str | None = None,
    department_id: str | None = None,
    status: str | None = None,
    role: str | None = None,
    municipality_id: str | None = None,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    q = select(User).order_by(User.created_at)
    if actor.role == "municipality_admin":
        q = q.where(User.municipality_id == actor.municipality_id)
    elif municipality_id:
        q = q.where(User.municipality_id == uuid.UUID(municipality_id))
    if search:
        like = f"%{search.lower()}%"
        q = q.where(
            or_(func.lower(User.email).like(like), func.lower(User.name).like(like))
        )
    if status:
        q = q.where(User.status == status)
    if role:
        q = q.where(User.role == role)
    users = db.scalars(q).all()
    out = [_out(db, u) for u in users]
    if department_id:
        out = [u for u in out if any(d.id == department_id for d in u.departments)]
    return out


@router.put("/{user_id}/departments", response_model=AdminUserOut)
def set_departments(
    user_id: uuid.UUID,
    body: DepartmentsPut,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _scoped_user_or_404(db, actor, user_id)
    dept_ids = [uuid.UUID(d) for d in body.department_ids]
    depts = list(db.scalars(select(Department).where(Department.id.in_(dept_ids))))
    if len(depts) != len(dept_ids) or any(
        d.municipality_id != user.municipality_id or d.status != "active" for d in depts
    ):
        raise HTTPException(status_code=404, detail="not_found")
    before = [str(d.id) for d in user.departments]
    user.departments = depts
    record_audit(
        db, actor_id=actor.id, action="user.set_departments", entity_type="user",
        entity_id=str(user.id), before={"department_ids": before},
        after={"department_ids": body.department_ids},
    )
    db.commit()
    return _out(db, user)


def _set_status(db: Session, actor: User, user: User, status: str, action: str) -> None:
    before = user.status
    user.status = status
    user.token_version += 1
    record_audit(
        db, actor_id=actor.id, action=action, entity_type="user",
        entity_id=str(user.id), before={"status": before}, after={"status": status},
    )
    db.commit()


@router.post("/{user_id}/deactivate", response_model=AdminUserOut)
def deactivate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _scoped_user_or_404(db, actor, user_id)
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="cannot_deactivate_self")
    _set_status(db, actor, user, "inactive", "user.deactivate")
    return _out(db, user)


@router.post("/{user_id}/reactivate", response_model=AdminUserOut)
def reactivate_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _scoped_user_or_404(db, actor, user_id)
    if user.status != "inactive":
        raise HTTPException(status_code=409, detail="not_inactive")
    _set_status(db, actor, user, "active", "user.reactivate")
    return _out(db, user)


@router.post("/{user_id}/promote", response_model=AdminUserOut)
def promote_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _scoped_user_or_404(db, actor, user_id)
    if user.role != "department_user":
        raise HTTPException(status_code=409, detail="not_department_user")
    user.role = "municipality_admin"
    user.token_version += 1  # role claim changes; force re-login
    record_audit(
        db, actor_id=actor.id, action="user.promote", entity_type="user",
        entity_id=str(user.id), before={"role": "department_user"},
        after={"role": "municipality_admin"},
    )
    db.commit()
    return _out(db, user)


@router.post("/{user_id}/demote", response_model=AdminUserOut)
def demote_user(
    user_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _scoped_user_or_404(db, actor, user_id)
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="last_admin_guard")
    if user.role != "municipality_admin":
        raise HTTPException(status_code=409, detail="not_municipality_admin")
    user.role = "department_user"
    user.token_version += 1
    record_audit(
        db, actor_id=actor.id, action="user.demote", entity_type="user",
        entity_id=str(user.id), before={"role": "municipality_admin"},
        after={"role": "department_user"},
    )
    db.commit()
    return _out(db, user)
