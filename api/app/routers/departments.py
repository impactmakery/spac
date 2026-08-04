import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_municipality_admin
from app.models import Department, Municipality, User, UserDepartment
from app.services.audit import record_audit

router = APIRouter(prefix="/api/departments", tags=["departments"])

ARCHIVE_DAYS = 90


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    municipality_id: str | None = None  # system admin only


class DepartmentOut(BaseModel):
    id: str
    name: str
    status: str
    member_count: int
    file_count: int
    created_at: datetime
    archive_expires_at: datetime | None


def _scope_municipality_id(
    actor: User, municipality_id: str | None
) -> uuid.UUID:
    if actor.role == "municipality_admin":
        assert actor.municipality_id is not None
        return actor.municipality_id
    if municipality_id is None:
        raise HTTPException(status_code=422, detail="municipality_required")
    return uuid.UUID(municipality_id)


def _get_scoped_or_404(
    db: Session, actor: User, department_id: uuid.UUID
) -> Department:
    dept = db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="not_found")
    if actor.role == "municipality_admin" and dept.municipality_id != actor.municipality_id:
        raise HTTPException(status_code=404, detail="not_found")
    return dept


def _name_conflict(db: Session, municipality_id: uuid.UUID, name: str,
                   exclude_id: uuid.UUID | None = None) -> bool:
    q = select(Department).where(
        Department.municipality_id == municipality_id,
        func.lower(Department.name) == name.lower(),
        Department.status == "active",
    )
    if exclude_id:
        q = q.where(Department.id != exclude_id)
    return db.scalar(q) is not None


def _out(db: Session, dept: Department) -> DepartmentOut:
    member_count = (
        db.scalar(
            select(func.count()).select_from(UserDepartment).where(
                UserDepartment.department_id == dept.id
            )
        )
        or 0
    )
    return DepartmentOut(
        id=str(dept.id), name=dept.name, status=dept.status,
        member_count=member_count, file_count=_file_count(db, dept.id),
        created_at=dept.created_at, archive_expires_at=dept.archive_expires_at,
    )


def _file_count(db: Session, department_id: uuid.UUID) -> int:
    """Department files arrive in Stage D/E; until then always zero."""
    try:
        from app.models import DepartmentFile  # type: ignore[attr-defined]
    except ImportError:
        return 0
    return (
        db.scalar(
            select(func.count()).where(DepartmentFile.department_id == department_id)
        )
        or 0
    )


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    status: str = "active",
    municipality_id: str | None = None,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> list[DepartmentOut]:
    muni_id = _scope_municipality_id(actor, municipality_id)
    rows = db.scalars(
        select(Department)
        .where(Department.municipality_id == muni_id, Department.status == status)
        .order_by(Department.created_at)
    ).all()
    return [_out(db, d) for d in rows]


@router.post("", status_code=201, response_model=DepartmentOut)
def create_department(
    body: DepartmentIn,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    muni_id = _scope_municipality_id(actor, body.municipality_id)
    if db.get(Municipality, muni_id) is None:
        raise HTTPException(status_code=404, detail="not_found")
    if _name_conflict(db, muni_id, body.name):
        raise HTTPException(status_code=409, detail="name_exists")
    dept = Department(municipality_id=muni_id, name=body.name)
    db.add(dept)
    db.flush()
    record_audit(
        db, actor_id=actor.id, action="department.create", entity_type="department",
        entity_id=str(dept.id), after={"name": body.name},
    )
    db.commit()
    return _out(db, dept)


@router.patch("/{department_id}", response_model=DepartmentOut)
def rename_department(
    department_id: uuid.UUID,
    body: DepartmentIn,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    dept = _get_scoped_or_404(db, actor, department_id)
    if _name_conflict(db, dept.municipality_id, body.name, exclude_id=dept.id):
        raise HTTPException(status_code=409, detail="name_exists")
    before = dept.name
    dept.name = body.name
    record_audit(
        db, actor_id=actor.id, action="department.rename", entity_type="department",
        entity_id=str(dept.id), before={"name": before}, after={"name": body.name},
    )
    db.commit()
    return _out(db, dept)


@router.post("/{department_id}/archive", response_model=DepartmentOut)
def archive_department(
    department_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    dept = _get_scoped_or_404(db, actor, department_id)
    if dept.status == "archived":
        raise HTTPException(status_code=409, detail="already_archived")
    dept.status = "archived"
    dept.archive_expires_at = datetime.now(UTC) + timedelta(days=ARCHIVE_DAYS)
    record_audit(
        db, actor_id=actor.id, action="department.archive", entity_type="department",
        entity_id=str(dept.id), before={"status": "active"},
        after={"status": "archived", "expires": dept.archive_expires_at.isoformat()},
    )
    db.commit()
    return _out(db, dept)


@router.post("/{department_id}/restore", response_model=DepartmentOut)
def restore_department(
    department_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    dept = _get_scoped_or_404(db, actor, department_id)
    if dept.status != "archived":
        raise HTTPException(status_code=409, detail="not_archived")
    if _name_conflict(db, dept.municipality_id, dept.name):
        raise HTTPException(status_code=409, detail="name_exists")
    dept.status = "active"
    dept.archive_expires_at = None
    record_audit(
        db, actor_id=actor.id, action="department.restore", entity_type="department",
        entity_id=str(dept.id), before={"status": "archived"}, after={"status": "active"},
    )
    db.commit()
    return _out(db, dept)
