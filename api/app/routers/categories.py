import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_system_admin
from app.models import Category, User
from app.services.audit import record_audit

router = APIRouter(prefix="/api/categories", tags=["categories"])


class CategoryIn(BaseModel):
    name_he: str = Field(min_length=1, max_length=80)
    # Optional: the users are Hebrew-speaking, and the English name is for the
    # people running the platform rather than for anyone using it.
    name_en: str | None = Field(default=None, max_length=80)


class CategoryOut(BaseModel):
    id: str
    name_he: str
    name_en: str | None
    item_count: int


def _item_count(db: Session, category_id: uuid.UUID) -> int:
    """Board items arrive in Stage E; until then every category is empty."""
    try:
        from app.models import BoardItem  # type: ignore[attr-defined]
    except ImportError:
        return 0
    return (
        db.scalar(select(func.count()).where(BoardItem.category_id == category_id)) or 0
    )


def _out(db: Session, c: Category) -> CategoryOut:
    return CategoryOut(
        id=str(c.id), name_he=c.name_he, name_en=c.name_en,
        item_count=_item_count(db, c.id),
    )


def _get_or_404(db: Session, category_id: uuid.UUID) -> Category:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="not_found")
    return cat


@router.get("", response_model=list[CategoryOut])
def list_categories(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CategoryOut]:
    return [_out(db, c) for c in db.scalars(select(Category).order_by(Category.name_he))]


@router.post("", status_code=201, response_model=CategoryOut)
def create_category(
    body: CategoryIn,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> CategoryOut:
    english = (body.name_en or "").strip() or None
    clash = func.lower(Category.name_he) == body.name_he.lower()
    if english:
        clash = clash | (func.lower(Category.name_en) == english.lower())
    if db.scalar(select(Category).where(clash)):
        raise HTTPException(status_code=409, detail="name_exists")
    cat = Category(name_he=body.name_he, name_en=english)
    db.add(cat)
    db.flush()
    record_audit(
        db, actor_id=actor.id, action="category.create", entity_type="category",
        entity_id=str(cat.id), after=body.model_dump(),
    )
    db.commit()
    return _out(db, cat)


@router.patch("/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: uuid.UUID,
    body: CategoryIn,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> CategoryOut:
    cat = _get_or_404(db, category_id)
    before = {"name_he": cat.name_he, "name_en": cat.name_en}
    cat.name_he = body.name_he
    cat.name_en = (body.name_en or "").strip() or None
    record_audit(
        db, actor_id=actor.id, action="category.rename", entity_type="category",
        entity_id=str(cat.id), before=before, after=body.model_dump(),
    )
    db.commit()
    return _out(db, cat)


@router.post("/{category_id}/merge-into/{target_id}")
def merge_category(
    category_id: uuid.UUID,
    target_id: uuid.UUID,
    actor: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> dict:
    if category_id == target_id:
        raise HTTPException(status_code=422, detail="same_category")
    source = _get_or_404(db, category_id)
    target = _get_or_404(db, target_id)
    moved = _reparent_items(db, source.id, target.id)
    record_audit(
        db, actor_id=actor.id, action="category.merge", entity_type="category",
        entity_id=str(source.id),
        before={"name_he": source.name_he, "moved_items": moved},
        after={"into": str(target.id)},
    )
    db.delete(source)
    db.commit()
    return {"ok": True, "moved_items": moved}


def _reparent_items(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> int:
    try:
        from app.models import BoardItem  # type: ignore[attr-defined]
    except ImportError:
        return 0
    from sqlalchemy import update
    from sqlalchemy.engine import CursorResult

    result = db.execute(
        update(BoardItem)
        .where(BoardItem.category_id == source_id)
        .values(category_id=target_id)
    )
    assert isinstance(result, CursorResult)
    return result.rowcount or 0
