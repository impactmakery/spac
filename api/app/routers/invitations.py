import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_municipality_admin
from app.models import Department, Invitation, User
from app.services.invitations import create_invitation, resend_invitation

router = APIRouter(prefix="/api/invitations", tags=["invitations"])


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(municipality_admin|department_user)$")
    municipality_id: str | None = None
    department_ids: list[str] = []
    language: str = Field(default="he", pattern="^(he|en)$")


class InvitationOut(BaseModel):
    id: str
    email: str
    role: str
    municipality_id: str | None
    department_ids: list[str]


def _out(inv: Invitation) -> InvitationOut:
    return InvitationOut(
        id=str(inv.id),
        email=inv.email,
        role=inv.role,
        municipality_id=str(inv.municipality_id) if inv.municipality_id else None,
        department_ids=list(inv.department_ids or []),
    )


@router.post("", status_code=201, response_model=InvitationOut)
def create(
    body: InvitationCreate,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> InvitationOut:
    if actor.role == "municipality_admin":
        if body.role != "department_user":
            raise HTTPException(status_code=403, detail="forbidden")
        municipality_id = actor.municipality_id
        if not body.department_ids:
            raise HTTPException(status_code=422, detail="department_required")
    else:  # system admin
        if body.role == "municipality_admin":
            if not body.municipality_id:
                raise HTTPException(status_code=422, detail="municipality_required")
            municipality_id = uuid.UUID(body.municipality_id)
        else:
            municipality_id = (
                uuid.UUID(body.municipality_id) if body.municipality_id else None
            )
            if not body.department_ids:
                raise HTTPException(status_code=422, detail="department_required")

    dept_ids = [uuid.UUID(d) for d in body.department_ids]
    if dept_ids:
        depts = list(db.scalars(select(Department).where(Department.id.in_(dept_ids))))
        if len(depts) != len(dept_ids) or any(
            d.municipality_id != municipality_id or d.status != "active" for d in depts
        ):
            # wrong-scope departments are indistinguishable from nonexistent ones
            raise HTTPException(status_code=404, detail="not_found")

    inv = create_invitation(
        db,
        email=body.email,
        role=body.role,
        municipality_id=municipality_id,
        department_ids=dept_ids,
        invited_by=actor,
        language=body.language,
    )
    return _out(inv)


@router.post("/{invitation_id}/resend", response_model=InvitationOut)
def resend(
    invitation_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> InvitationOut:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="not_found")
    if actor.role == "municipality_admin" and inv.municipality_id != actor.municipality_id:
        raise HTTPException(status_code=404, detail="not_found")
    if inv.used_at is not None:
        raise HTTPException(status_code=409, detail="already_accepted")
    resend_invitation(db, invitation=inv, actor=actor)
    return _out(inv)
