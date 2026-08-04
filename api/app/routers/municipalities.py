import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_system_admin
from app.models import Department, Municipality, User
from app.services.audit import record_audit

router = APIRouter(prefix="/api/municipalities", tags=["municipalities"])


class MunicipalityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MunicipalityOut(BaseModel):
    id: str
    name: str
    status: str
    admin_names: list[str]
    user_count: int
    department_count: int
    created_at: datetime


def _get_or_404(db: Session, municipality_id: uuid.UUID) -> Municipality:
    muni = db.get(Municipality, municipality_id)
    if muni is None:
        raise HTTPException(status_code=404, detail="not_found")
    return muni


def _name_conflict(db: Session, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    q = select(Municipality).where(
        func.lower(Municipality.name) == name.lower(), Municipality.status == "active"
    )
    if exclude_id:
        q = q.where(Municipality.id != exclude_id)
    return db.scalar(q) is not None


@router.get("", response_model=list[MunicipalityOut])
def list_municipalities(
    actor: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> list[MunicipalityOut]:
    rows = db.scalars(select(Municipality).order_by(Municipality.created_at)).all()
    out = []
    for muni in rows:
        admins = db.scalars(
            select(User.name).where(
                User.municipality_id == muni.id,
                User.role == "municipality_admin",
                User.status == "active",
            )
        ).all()
        out.append(
            MunicipalityOut(
                id=str(muni.id),
                name=muni.name,
                status=muni.status,
                admin_names=[a for a in admins if a],
                user_count=db.scalar(
                    select(func.count(User.id)).where(User.municipality_id == muni.id)
                )
                or 0,
                department_count=db.scalar(
                    select(func.count(Department.id)).where(
                        Department.municipality_id == muni.id,
                        Department.status == "active",
                    )
                )
                or 0,
                created_at=muni.created_at,
            )
        )
    return out


@router.post("", status_code=201, response_model=MunicipalityOut)
def create_municipality(
    body: MunicipalityIn,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> MunicipalityOut:
    if _name_conflict(db, body.name):
        raise HTTPException(status_code=409, detail="name_exists")
    muni = Municipality(name=body.name)
    db.add(muni)
    db.flush()
    record_audit(
        db, actor_id=actor.id, action="municipality.create",
        entity_type="municipality", entity_id=str(muni.id), after={"name": body.name},
    )
    db.commit()
    return MunicipalityOut(
        id=str(muni.id), name=muni.name, status=muni.status, admin_names=[],
        user_count=0, department_count=0, created_at=muni.created_at,
    )


@router.patch("/{municipality_id}")
def rename_municipality(
    municipality_id: uuid.UUID,
    body: MunicipalityIn,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> dict:
    muni = _get_or_404(db, municipality_id)
    if _name_conflict(db, body.name, exclude_id=muni.id):
        raise HTTPException(status_code=409, detail="name_exists")
    before = muni.name
    muni.name = body.name
    record_audit(
        db, actor_id=actor.id, action="municipality.rename",
        entity_type="municipality", entity_id=str(muni.id),
        before={"name": before}, after={"name": body.name},
    )
    db.commit()
    return {"ok": True}


def _set_status(db: Session, actor: User, muni: Municipality, status: str) -> None:
    before = muni.status
    muni.status = status
    if status == "inactive":
        # Kill every session in the municipality within the 60 s bound.
        for user in db.scalars(select(User).where(User.municipality_id == muni.id)):
            user.token_version += 1
    record_audit(
        db, actor_id=actor.id, action=f"municipality.{status}",
        entity_type="municipality", entity_id=str(muni.id),
        before={"status": before}, after={"status": status},
    )
    db.commit()


@router.post("/{municipality_id}/deactivate")
def deactivate_municipality(
    municipality_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> dict:
    _set_status(db, actor, _get_or_404(db, municipality_id), "inactive")
    return {"ok": True}


@router.post("/{municipality_id}/reactivate")
def reactivate_municipality(
    municipality_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> dict:
    _set_status(db, actor, _get_or_404(db, municipality_id), "active")
    return {"ok": True}
