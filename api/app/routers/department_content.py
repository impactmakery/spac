import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Chunk,
    Department,
    DepartmentFile,
    DepartmentPost,
    DepartmentPostComment,
    IngestionJob,
    User,
    UserDepartment,
)
from app.services.ingestion import enqueue
from app.services.storage import get_storage
from app.services.uploads import validate_upload

router = APIRouter(prefix="/api/departments", tags=["department-content"])

MAX_POST = 2000
MAX_COMMENT = 1000


def _require_department_access(
    db: Session, user: User, department_id: uuid.UUID
) -> Department:
    dept = db.get(Department, department_id)
    if dept is None or dept.status != "active":
        raise HTTPException(status_code=404, detail="not_found")
    if user.role == "system_admin":
        return dept
    if (
        user.role == "municipality_admin"
        and dept.municipality_id == user.municipality_id
    ):
        return dept
    member = db.get(
        UserDepartment, {"user_id": user.id, "department_id": department_id}
    )
    if member is None:
        raise HTTPException(status_code=404, detail="not_found")
    return dept


class AuthorRef(BaseModel):
    id: str | None
    name: str | None
    inactive: bool


def _author(db: Session, author_id: uuid.UUID | None) -> AuthorRef:
    user = db.get(User, author_id) if author_id else None
    return AuthorRef(
        id=str(user.id) if user else None,
        name=user.name if user else None,
        inactive=bool(user and user.status == "inactive"),
    )


class DeptFileOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    status: str
    uploader: AuthorRef
    download_url: str
    can_delete: bool
    created_at: datetime


class DeptInfoOut(BaseModel):
    id: str
    name: str


def _file_out(db: Session, f: DepartmentFile, user: User) -> DeptFileOut:
    can_delete = (
        f.uploader_id == user.id
        or user.role == "system_admin"
        or user.role == "municipality_admin"
    )
    return DeptFileOut(
        id=str(f.id),
        filename=f.filename,
        size_bytes=f.size_bytes,
        status=f.status,
        uploader=_author(db, f.uploader_id),
        download_url=get_storage().download_url(f.storage_key, f.filename),
        can_delete=can_delete,
        created_at=f.created_at,
    )


@router.get("/{department_id}/info", response_model=DeptInfoOut)
def department_info(
    department_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeptInfoOut:
    dept = _require_department_access(db, user, department_id)
    return DeptInfoOut(id=str(dept.id), name=dept.name)


@router.get("/{department_id}/files", response_model=list[DeptFileOut])
def list_files(
    department_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeptFileOut]:
    _require_department_access(db, user, department_id)
    files = db.scalars(
        select(DepartmentFile)
        .where(DepartmentFile.department_id == department_id)
        .order_by(DepartmentFile.created_at.desc())
    ).all()
    return [_file_out(db, f, user) for f in files]


@router.post("/{department_id}/files", status_code=201, response_model=DeptFileOut)
async def upload_file(
    department_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeptFileOut:
    dept = _require_department_access(db, user, department_id)
    content = await file.read()
    filename = file.filename or "file"
    ext, content_type = validate_upload(filename, content, file.content_type or "")
    f = DepartmentFile(
        department_id=dept.id,
        uploader_id=user.id,
        filename=filename,
        storage_key=f"department/{dept.id}/{int(time.time())}/{filename}",
        size_bytes=len(content),
        content_type=content_type,
    )
    db.add(f)
    db.flush()
    get_storage().put(f.storage_key, content, content_type)
    enqueue(
        db,
        source_type="department",
        source_id=f.id,
        visibility="department",
        storage_key=f.storage_key,
        ext=ext,
        municipality_id=dept.municipality_id,
        department_id=dept.id,
    )
    db.commit()
    return _file_out(db, f, user)


@router.delete("/{department_id}/files/{file_id}")
def delete_file(
    department_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_department_access(db, user, department_id)
    f = db.get(DepartmentFile, file_id)
    if f is None or f.department_id != department_id:
        raise HTTPException(status_code=404, detail="not_found")
    if f.uploader_id != user.id and user.role == "department_user":
        raise HTTPException(status_code=404, detail="not_found")
    storage_key = f.storage_key
    db.execute(
        delete(Chunk).where(Chunk.source_type == "department", Chunk.source_id == f.id)
    )
    db.execute(
        delete(IngestionJob).where(
            IngestionJob.source_type == "department", IngestionJob.source_id == f.id
        )
    )
    db.delete(f)
    db.commit()
    get_storage().delete(storage_key)
    return {"ok": True}


class CommentOut(BaseModel):
    id: str
    author: AuthorRef
    body: str
    can_delete: bool
    created_at: datetime


class PostOut(BaseModel):
    id: str
    author: AuthorRef
    body: str
    can_delete: bool
    comments: list[CommentOut]
    created_at: datetime


def _post_out(db: Session, post: DepartmentPost, user: User) -> PostOut:
    can_moderate = user.role in ("system_admin", "municipality_admin")
    comments = db.scalars(
        select(DepartmentPostComment)
        .where(DepartmentPostComment.post_id == post.id)
        .order_by(DepartmentPostComment.created_at)
    ).all()
    return PostOut(
        id=str(post.id),
        author=_author(db, post.author_id),
        body=post.body,
        can_delete=post.author_id == user.id or can_moderate,
        comments=[
            CommentOut(
                id=str(c.id),
                author=_author(db, c.author_id),
                body=c.body,
                can_delete=c.author_id == user.id or can_moderate,
                created_at=c.created_at,
            )
            for c in comments
        ],
        created_at=post.created_at,
    )


@router.get("/{department_id}/posts", response_model=list[PostOut])
def list_posts(
    department_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    _require_department_access(db, user, department_id)
    posts = db.scalars(
        select(DepartmentPost)
        .where(DepartmentPost.department_id == department_id)
        .order_by(DepartmentPost.created_at.desc())
    ).all()
    return [_post_out(db, p, user) for p in posts]


class PostIn(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_POST)


@router.post("/{department_id}/posts", status_code=201, response_model=PostOut)
def create_post(
    department_id: uuid.UUID,
    body: PostIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostOut:
    dept = _require_department_access(db, user, department_id)
    post = DepartmentPost(department_id=dept.id, author_id=user.id, body=body.body)
    db.add(post)
    db.flush()
    enqueue(
        db,
        source_type="department",
        source_id=post.id,
        visibility="department",
        text_content=body.body,
        municipality_id=dept.municipality_id,
        department_id=dept.id,
    )
    db.commit()
    return _post_out(db, post, user)


@router.delete("/{department_id}/posts/{post_id}")
def delete_post(
    department_id: uuid.UUID,
    post_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_department_access(db, user, department_id)
    post = db.get(DepartmentPost, post_id)
    if post is None or post.department_id != department_id:
        raise HTTPException(status_code=404, detail="not_found")
    if post.author_id != user.id and user.role == "department_user":
        raise HTTPException(status_code=404, detail="not_found")
    db.execute(
        delete(Chunk).where(
            Chunk.source_type == "department", Chunk.source_id == post.id
        )
    )
    db.execute(
        delete(IngestionJob).where(
            IngestionJob.source_type == "department", IngestionJob.source_id == post.id
        )
    )
    db.delete(post)
    db.commit()
    return {"ok": True}


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT)


@router.post(
    "/{department_id}/posts/{post_id}/comments", status_code=201, response_model=CommentOut
)
def add_post_comment(
    department_id: uuid.UUID,
    post_id: uuid.UUID,
    body: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    _require_department_access(db, user, department_id)
    post = db.get(DepartmentPost, post_id)
    if post is None or post.department_id != department_id:
        raise HTTPException(status_code=404, detail="not_found")
    comment = DepartmentPostComment(post_id=post.id, author_id=user.id, body=body.body)
    db.add(comment)
    db.commit()
    return CommentOut(
        id=str(comment.id),
        author=_author(db, user.id),
        body=comment.body,
        can_delete=True,
        created_at=comment.created_at,
    )


@router.delete("/{department_id}/posts/{post_id}/comments/{comment_id}")
def delete_post_comment(
    department_id: uuid.UUID,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_department_access(db, user, department_id)
    comment = db.get(DepartmentPostComment, comment_id)
    if comment is None or comment.post_id != post_id:
        raise HTTPException(status_code=404, detail="not_found")
    if comment.author_id != user.id and user.role == "department_user":
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(comment)
    db.commit()
    return {"ok": True}
