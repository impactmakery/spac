from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User
from app.routers.auth import user_out
from app.schemas.auth import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


class MePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    language: str | None = Field(default=None, pattern="^(he|en)$")
    digest_enabled: bool | None = None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)


class DepartmentRef(BaseModel):
    id: str
    name: str


@router.get("/me/departments", response_model=list[DepartmentRef])
def my_departments(user: User = Depends(get_current_user)) -> list[DepartmentRef]:
    return [
        DepartmentRef(id=str(d.id), name=d.name)
        for d in user.departments
        if d.status == "active"
    ]


@router.patch("/me", response_model=UserOut)
def patch_me(
    body: MePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if body.name is not None:
        user.name = body.name
    if body.language is not None:
        user.language = body.language
    if body.digest_enabled is not None:
        user.digest_enabled = body.digest_enabled
    db.commit()
    return user_out(user)
