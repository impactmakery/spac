import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    BoardComment,
    BoardItem,
    BoardLike,
    Category,
    Chunk,
    IngestionJob,
    Municipality,
    User,
)
from app.services.audit import record_audit
from app.services.ingestion import enqueue
from app.services.storage import get_storage
from app.services.uploads import validate_upload

router = APIRouter(prefix="/api/board-items", tags=["boards"])

PAGE_SIZE = 30
MAX_TITLE = 120
MAX_DESCRIPTION = 2000
MAX_COMMENT = 1000


class CategoryRef(BaseModel):
    id: str
    name_he: str
    name_en: str


class AuthorRef(BaseModel):
    id: str | None
    name: str | None
    municipality_name: str | None
    inactive: bool


class BoardItemOut(BaseModel):
    id: str
    title: str
    description: str | None
    category: CategoryRef
    scope: str
    author: AuthorRef
    link_url: str | None
    filename: str | None
    size_bytes: int | None
    like_count: int
    comment_count: int
    liked_by_me: bool
    can_edit: bool
    can_delete: bool
    created_at: datetime


class CommentOut(BaseModel):
    id: str
    author: AuthorRef
    body: str
    can_delete: bool
    created_at: datetime


class BoardItemDetail(BoardItemOut):
    download_url: str | None
    comments: list[CommentOut]


class BoardPage(BaseModel):
    items: list[BoardItemOut]
    has_more: bool


def _author_ref(db: Session, author_id: uuid.UUID | None) -> AuthorRef:
    author = db.get(User, author_id) if author_id else None
    muni = (
        db.get(Municipality, author.municipality_id)
        if author and author.municipality_id
        else None
    )
    return AuthorRef(
        id=str(author.id) if author else None,
        name=author.name if author else None,
        municipality_name=muni.name if muni else None,
        inactive=bool(author and author.status == "inactive"),
    )


def _can_delete(db: Session, item: BoardItem, user: User) -> bool:
    if user.role == "system_admin" or item.author_id == user.id:
        return True
    if user.role != "municipality_admin":
        return False
    if item.scope == "municipality":
        return item.municipality_id == user.municipality_id
    # global board: may moderate their own municipality's members' items
    author = db.get(User, item.author_id) if item.author_id else None
    return bool(author and author.municipality_id == user.municipality_id)


def _visible_or_404(item: BoardItem, user: User) -> None:
    if item.scope == "municipality" and user.role != "system_admin":
        if item.municipality_id != user.municipality_id:
            raise HTTPException(status_code=404, detail="not_found")


def _out(db: Session, item: BoardItem, user: User) -> BoardItemOut:
    cat = db.get(Category, item.category_id)
    like_count = (
        db.scalar(select(func.count()).where(BoardLike.item_id == item.id)) or 0
    )
    comment_count = (
        db.scalar(select(func.count()).where(BoardComment.item_id == item.id)) or 0
    )
    liked = (
        db.get(BoardLike, {"item_id": item.id, "user_id": user.id}) is not None
    )
    assert cat is not None
    return BoardItemOut(
        id=str(item.id),
        title=item.title,
        description=item.description,
        category=CategoryRef(id=str(cat.id), name_he=cat.name_he, name_en=cat.name_en),
        scope=item.scope,
        author=_author_ref(db, item.author_id),
        link_url=item.link_url,
        filename=item.filename,
        size_bytes=item.size_bytes,
        like_count=like_count,
        comment_count=comment_count,
        liked_by_me=liked,
        can_edit=item.author_id == user.id,
        can_delete=_can_delete(db, item, user),
        created_at=item.created_at,
    )


@router.get("", response_model=BoardPage)
def list_items(
    scope: str = "global",
    search: str | None = None,
    category_id: str | None = None,
    sort: str = "newest",
    page: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardPage:
    q = select(BoardItem)
    if scope == "municipality":
        if user.municipality_id is None:
            raise HTTPException(status_code=404, detail="not_found")
        q = q.where(
            BoardItem.scope == "municipality",
            BoardItem.municipality_id == user.municipality_id,
        )
    else:
        q = q.where(BoardItem.scope == "global")
    if category_id:
        q = q.where(BoardItem.category_id == uuid.UUID(category_id))
    if search:
        like = f"%{search.lower()}%"
        q = q.where(
            BoardItem.search.op("@@")(func.plainto_tsquery("simple", search))
            | func.lower(BoardItem.title).like(like)
            | func.lower(func.coalesce(BoardItem.description, "")).like(like)
        )
    if sort == "liked":
        like_counts = (
            select(BoardLike.item_id, func.count().label("n"))
            .group_by(BoardLike.item_id)
            .subquery()
        )
        q = q.outerjoin(like_counts, like_counts.c.item_id == BoardItem.id).order_by(
            func.coalesce(like_counts.c.n, 0).desc(), BoardItem.created_at.desc()
        )
    else:
        q = q.order_by(BoardItem.created_at.desc())
    rows = db.scalars(q.offset(page * PAGE_SIZE).limit(PAGE_SIZE + 1)).all()
    return BoardPage(
        items=[_out(db, i, user) for i in rows[:PAGE_SIZE]],
        has_more=len(rows) > PAGE_SIZE,
    )


def _validate_common(
    db: Session, *, title: str, description: str | None, category_id: str,
    link_url: str | None, has_file: bool,
) -> Category:
    if not title or len(title) > MAX_TITLE:
        raise HTTPException(status_code=422, detail="invalid_title")
    if description and len(description) > MAX_DESCRIPTION:
        raise HTTPException(status_code=422, detail="invalid_description")
    if bool(link_url) == has_file:  # exactly one of file XOR link
        raise HTTPException(status_code=422, detail="file_or_link_required")
    if link_url and not link_url.startswith("https://"):
        raise HTTPException(status_code=422, detail="link_must_be_https")
    cat = db.get(Category, uuid.UUID(category_id))
    if cat is None:
        raise HTTPException(status_code=422, detail="invalid_category")
    return cat


def _resolve_scope(
    user: User, destination: str, municipality_id: str | None
) -> tuple[str, uuid.UUID | None]:
    if destination == "global":
        return "global", None
    if user.role == "system_admin":
        if not municipality_id:
            raise HTTPException(status_code=422, detail="municipality_required")
        return "municipality", uuid.UUID(municipality_id)
    if user.municipality_id is None:
        raise HTTPException(status_code=422, detail="municipality_required")
    return "municipality", user.municipality_id


def _enqueue_item(db: Session, item: BoardItem) -> None:
    ext = item.filename.rsplit(".", 1)[-1].lower() if item.filename else None
    item.indexing_status = "pending"
    enqueue(
        db,
        source_type="board",
        source_id=item.id,
        visibility="global" if item.scope == "global" else "municipality",
        storage_key=item.storage_key,
        ext=ext,
        text_content=item.description or "",
        title=item.title,
        municipality_id=item.municipality_id,
    )


@router.post("", status_code=201, response_model=BoardItemOut)
async def create_item(
    title: str = Form(...),
    category_id: str = Form(...),
    destination: str = Form(...),
    description: str | None = Form(default=None),
    link_url: str | None = Form(default=None),
    municipality_id: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardItemOut:
    content = await file.read() if file else None
    _validate_common(
        db, title=title, description=description, category_id=category_id,
        link_url=link_url, has_file=content is not None,
    )
    scope, muni_id = _resolve_scope(user, destination, municipality_id)

    item = BoardItem(
        title=title,
        description=description or None,
        category_id=uuid.UUID(category_id),
        scope=scope,
        municipality_id=muni_id,
        author_id=user.id,
        link_url=link_url or None,
    )
    db.add(item)
    db.flush()
    if content is not None and file is not None:
        filename = file.filename or "file"
        ext, content_type = validate_upload(filename, content, file.content_type or "")
        item.filename = filename
        item.size_bytes = len(content)
        item.content_type = content_type
        item.storage_key = f"board/{item.id}/{int(time.time())}/{filename}"
        get_storage().put(item.storage_key, content, content_type)
    _enqueue_item(db, item)
    db.commit()
    return _out(db, item, user)


def _get_item_or_404(db: Session, item_id: uuid.UUID, user: User) -> BoardItem:
    item = db.get(BoardItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    _visible_or_404(item, user)
    return item


@router.get("/{item_id}", response_model=BoardItemDetail)
def get_item(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardItemDetail:
    item = _get_item_or_404(db, item_id, user)
    base = _out(db, item, user)
    comments = db.scalars(
        select(BoardComment)
        .where(BoardComment.item_id == item.id)
        .order_by(BoardComment.created_at)
    ).all()
    return BoardItemDetail(
        **base.model_dump(),
        download_url=(
            get_storage().download_url(item.storage_key, item.filename or "file")
            if item.storage_key
            else None
        ),
        comments=[
            CommentOut(
                id=str(c.id),
                author=_author_ref(db, c.author_id),
                body=c.body,
                can_delete=c.author_id == user.id or _can_delete(db, item, user),
                created_at=c.created_at,
            )
            for c in comments
        ],
    )


class ItemPatch(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    category_id: str


@router.patch("/{item_id}", response_model=BoardItemOut)
def edit_item(
    item_id: uuid.UUID,
    body: ItemPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardItemOut:
    item = _get_item_or_404(db, item_id, user)
    if item.author_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    if db.get(Category, uuid.UUID(body.category_id)) is None:
        raise HTTPException(status_code=422, detail="invalid_category")
    item.title = body.title
    item.description = body.description or None
    item.category_id = uuid.UUID(body.category_id)
    _enqueue_item(db, item)
    db.commit()
    return _out(db, item, user)


@router.delete("/{item_id}")
def delete_item(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    item = _get_item_or_404(db, item_id, user)
    if not _can_delete(db, item, user):
        raise HTTPException(status_code=404, detail="not_found")
    storage_key = item.storage_key
    db.execute(
        delete(Chunk).where(Chunk.source_type == "board", Chunk.source_id == item.id)
    )
    db.execute(
        delete(IngestionJob).where(
            IngestionJob.source_type == "board", IngestionJob.source_id == item.id
        )
    )
    if item.author_id != user.id:
        record_audit(
            db, actor_id=user.id, action="board_item.moderate_delete",
            entity_type="board_item", entity_id=str(item.id),
            before={"title": item.title, "author_id": str(item.author_id)},
        )
    db.delete(item)  # comments + likes cascade via FK
    db.commit()
    if storage_key:
        get_storage().delete(storage_key)
    return {"ok": True}


@router.post("/{item_id}/like")
def toggle_like(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    item = _get_item_or_404(db, item_id, user)
    existing = db.get(BoardLike, {"item_id": item.id, "user_id": user.id})
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(BoardLike(item_id=item.id, user_id=user.id))
        liked = True
    db.commit()
    count = db.scalar(select(func.count()).where(BoardLike.item_id == item.id)) or 0
    return {"liked": liked, "like_count": count}


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT)


@router.post("/{item_id}/comments", status_code=201, response_model=CommentOut)
def add_comment(
    item_id: uuid.UUID,
    body: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    item = _get_item_or_404(db, item_id, user)
    comment = BoardComment(item_id=item.id, author_id=user.id, body=body.body)
    db.add(comment)
    db.commit()
    return CommentOut(
        id=str(comment.id),
        author=_author_ref(db, user.id),
        body=comment.body,
        can_delete=True,
        created_at=comment.created_at,
    )


@router.delete("/{item_id}/comments/{comment_id}")
def delete_comment(
    item_id: uuid.UUID,
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    item = _get_item_or_404(db, item_id, user)
    comment = db.get(BoardComment, comment_id)
    if comment is None or comment.item_id != item.id:
        raise HTTPException(status_code=404, detail="not_found")
    if comment.author_id != user.id and not _can_delete(db, item, user):
        raise HTTPException(status_code=404, detail="not_found")
    if comment.author_id != user.id:
        record_audit(
            db, actor_id=user.id, action="board_comment.moderate_delete",
            entity_type="board_comment", entity_id=str(comment.id),
            before={"body": comment.body[:200]},
        )
    db.delete(comment)
    db.commit()
    return {"ok": True}
