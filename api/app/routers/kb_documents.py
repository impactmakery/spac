import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_municipality_admin
from app.models import Chunk, IngestionJob, KbDocument, Municipality, User
from app.services.audit import record_audit
from app.services.ingestion import enqueue
from app.services.storage import get_storage
from app.services.uploads import validate_upload

router = APIRouter(prefix="/api/kb-documents", tags=["kb"])


class KbDocOut(BaseModel):
    id: str
    title: str
    filename: str
    size_bytes: int
    content_type: str
    status: str
    uploader_name: str | None
    municipality_name: str | None  # None = Program (system admin upload)
    uploader_id: str | None
    created_at: datetime
    updated_at: datetime


class KbDocDetail(KbDocOut):
    download_url: str
    error: str | None


def _out(db: Session, doc: KbDocument) -> KbDocOut:
    uploader = db.get(User, doc.uploader_id) if doc.uploader_id else None
    muni = db.get(Municipality, doc.municipality_id) if doc.municipality_id else None
    return KbDocOut(
        id=str(doc.id),
        title=doc.title,
        filename=doc.filename,
        size_bytes=doc.size_bytes,
        content_type=doc.content_type,
        status=doc.status,
        uploader_name=uploader.name if uploader else None,
        municipality_name=muni.name if muni else None,
        uploader_id=str(doc.uploader_id) if doc.uploader_id else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _get_or_404(db: Session, doc_id: uuid.UUID) -> KbDocument:
    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="not_found")
    return doc


def _require_owner_or_sysadmin(doc: KbDocument, user: User) -> None:
    if user.role == "system_admin":
        return
    if doc.uploader_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")


def _storage_key(doc_id: uuid.UUID, filename: str) -> str:
    return f"kb/{doc_id}/{int(time.time())}/{filename}"


@router.get("", response_model=list[KbDocOut])
def list_documents(
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KbDocOut]:
    q = select(KbDocument).order_by(KbDocument.created_at.desc())
    if search:
        q = q.where(func.lower(KbDocument.title).like(f"%{search.lower()}%"))
    return [_out(db, d) for d in db.scalars(q)]


@router.get("/{doc_id}", response_model=KbDocDetail)
def get_document(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KbDocDetail:
    doc = _get_or_404(db, doc_id)
    base = _out(db, doc)
    return KbDocDetail(
        **base.model_dump(),
        download_url=get_storage().download_url(doc.storage_key, doc.filename),
        error=doc.error if (user.role == "system_admin" or doc.uploader_id == user.id) else None,
    )


@router.post("", status_code=201, response_model=KbDocOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> KbDocOut:
    content = await file.read()
    filename = file.filename or "document"
    ext, content_type = validate_upload(filename, content, file.content_type or "")

    doc = KbDocument(
        title=title or filename.rsplit(".", 1)[0],
        filename=filename,
        storage_key="",
        size_bytes=len(content),
        content_type=content_type,
        uploader_id=actor.id,
        municipality_id=actor.municipality_id,
    )
    db.add(doc)
    db.flush()
    doc.storage_key = _storage_key(doc.id, filename)
    get_storage().put(doc.storage_key, content, content_type)
    enqueue(
        db, source_type="kb", source_id=doc.id, visibility="global",
        storage_key=doc.storage_key, ext=ext,
    )
    record_audit(
        db, actor_id=actor.id, action="kb_document.upload", entity_type="kb_document",
        entity_id=str(doc.id), after={"title": doc.title, "filename": filename},
    )
    db.commit()
    return _out(db, doc)


@router.post("/{doc_id}/replace", response_model=KbDocOut)
async def replace_document(
    doc_id: uuid.UUID,
    file: UploadFile = File(...),
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> KbDocOut:
    doc = _get_or_404(db, doc_id)
    _require_owner_or_sysadmin(doc, actor)
    content = await file.read()
    filename = file.filename or doc.filename
    ext, content_type = validate_upload(filename, content, file.content_type or "")

    old_key = doc.storage_key
    doc.filename = filename
    doc.size_bytes = len(content)
    doc.content_type = content_type
    doc.status = "pending"
    doc.error = None
    doc.storage_key = _storage_key(doc.id, filename)
    get_storage().put(doc.storage_key, content, content_type)
    enqueue(
        db, source_type="kb", source_id=doc.id, visibility="global",
        storage_key=doc.storage_key, ext=ext,
    )
    record_audit(
        db, actor_id=actor.id, action="kb_document.replace", entity_type="kb_document",
        entity_id=str(doc.id), before={"storage_key": old_key},
        after={"filename": filename},
    )
    db.commit()
    if old_key:
        get_storage().delete(old_key)
    return _out(db, doc)


@router.delete("/{doc_id}")
def delete_document(
    doc_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get_or_404(db, doc_id)
    _require_owner_or_sysadmin(doc, actor)
    storage_key = doc.storage_key
    # document, its chunks, and its queue entries die in ONE transaction (spec)
    db.execute(delete(Chunk).where(Chunk.source_type == "kb", Chunk.source_id == doc.id))
    db.execute(
        delete(IngestionJob).where(
            IngestionJob.source_type == "kb", IngestionJob.source_id == doc.id
        )
    )
    record_audit(
        db, actor_id=actor.id, action="kb_document.delete", entity_type="kb_document",
        entity_id=str(doc.id), before={"title": doc.title},
    )
    db.delete(doc)
    db.commit()
    if storage_key:
        get_storage().delete(storage_key)
    return {"ok": True}


@router.post("/{doc_id}/retry", response_model=KbDocOut)
def retry_document(
    doc_id: uuid.UUID,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> KbDocOut:
    doc = _get_or_404(db, doc_id)
    _require_owner_or_sysadmin(doc, actor)
    ext = doc.filename.rsplit(".", 1)[-1].lower()
    doc.status = "pending"
    doc.error = None
    enqueue(
        db, source_type="kb", source_id=doc.id, visibility="global",
        storage_key=doc.storage_key, ext=ext,
    )
    db.commit()
    return _out(db, doc)
