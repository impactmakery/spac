import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_municipality_admin
from app.models import Chunk, IngestionJob, KbDocument, Municipality, User
from app.rag.extract import extract_text
from app.services.audit import record_audit
from app.services.ingestion import enqueue
from app.services.storage import get_storage
from app.services.uploads import is_extractable, validate_upload

router = APIRouter(prefix="/api/kb-documents", tags=["kb"])


class KbDocOut(BaseModel):
    id: str
    title: str
    filename: str
    size_bytes: int
    content_type: str
    status: str
    scope: str
    uploader_name: str | None
    municipality_name: str | None  # None = Program (system admin upload)
    municipality_id: str | None
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
        scope=doc.scope,
        uploader_name=uploader.name if uploader else None,
        municipality_name=muni.name if muni else None,
        municipality_id=str(doc.municipality_id) if doc.municipality_id else None,
        uploader_id=str(doc.uploader_id) if doc.uploader_id else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _readable(user: User) -> ColumnElement[bool]:
    """Which documents this person may read, as a WHERE clause.

    The shared library is readable by everyone; a municipality's library only
    by that municipality. Expressed as SQL rather than a post-filter so a
    listing and a lookup cannot drift apart.
    """
    if user.role == "system_admin":
        return KbDocument.id.is_not(None)
    return or_(
        KbDocument.scope == "global",
        KbDocument.municipality_id == user.municipality_id,
    )


def _get_or_404(db: Session, doc_id: uuid.UUID, user: User) -> KbDocument:
    doc = db.scalar(select(KbDocument).where(KbDocument.id == doc_id, _readable(user)))
    if doc is None:
        # 404 rather than 403: another municipality's library must not be
        # confirmed to exist by the shape of the error.
        raise HTTPException(status_code=404, detail="not_found")
    return doc


def _require_manager(doc: KbDocument, user: User) -> None:
    """Who may change a document.

    The shared library is curated centrally, so only a system admin edits it.
    A municipality's own library is managed by that municipality's admins —
    all of them, not just whoever uploaded, or a library would fragment the
    moment one administrator left.
    """
    if user.role == "system_admin":
        return
    if doc.scope == "municipality" and doc.municipality_id == user.municipality_id:
        return
    raise HTTPException(status_code=404, detail="not_found")


def _storage_key(doc_id: uuid.UUID, filename: str) -> str:
    return f"kb/{doc_id}/{int(time.time())}/{filename}"


@router.get("", response_model=list[KbDocOut])
def list_documents(
    search: str | None = None,
    scope: str | None = None,
    municipality_id: uuid.UUID | None = None,
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> list[KbDocOut]:
    """Browse the library. Administrators only.

    The knowledge base is curated centrally, so department users no longer see
    it as a place to visit — they reach its contents through the assistant.
    Individual documents stay readable by anyone who may see them (see
    get_document), or a citation would lead somewhere they cannot open.
    """
    q = select(KbDocument).where(_readable(actor)).order_by(KbDocument.created_at.desc())
    if search:
        q = q.where(func.lower(KbDocument.title).like(f"%{search.lower()}%"))
    if scope in ("global", "municipality"):
        q = q.where(KbDocument.scope == scope)
    if municipality_id is not None:
        q = q.where(KbDocument.municipality_id == municipality_id)
    return [_out(db, d) for d in db.scalars(q)]


@router.get("/{doc_id}", response_model=KbDocDetail)
def get_document(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KbDocDetail:
    doc = _get_or_404(db, doc_id, user)
    base = _out(db, doc)
    may_manage = user.role == "system_admin" or (
        doc.scope == "municipality"
        and doc.municipality_id == user.municipality_id
        and user.role == "municipality_admin"
    )
    return KbDocDetail(
        **base.model_dump(),
        download_url=get_storage().download_url(
            doc.storage_key, doc.filename, content_type=doc.content_type
        ),
        error=doc.error if (may_manage or doc.uploader_id == user.id) else None,
    )


class TextPreviewOut(BaseModel):
    text: str
    truncated: bool
    available: bool


# Long enough for any circular or procedure, short enough that a 300-page
# scan does not arrive as one payload.
MAX_PREVIEW_CHARS = 200_000


@router.get("/{doc_id}/text", response_model=TextPreviewOut)
def document_text(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TextPreviewOut:
    """The document's text, for previewing formats a browser cannot render.

    Word, PowerPoint and Excel files cannot be shown in a frame, and converting
    them server-side would mean carrying an office suite in the image. The text
    is already extracted for the assistant, so reusing it answers "what is in
    this document?" — which is what a preview is for — at no new cost.

    Reachable by anyone who may read the document itself: everyone for the
    shared library, one municipality for its own.
    """
    doc = _get_or_404(db, doc_id, user)
    ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
    if not is_extractable(ext):
        return TextPreviewOut(text="", truncated=False, available=False)

    try:
        content = get_storage().open(doc.storage_key)
        text = extract_text(content, ext)
    except Exception:  # noqa: BLE001 — a preview must never break the page
        return TextPreviewOut(text="", truncated=False, available=False)

    truncated = len(text) > MAX_PREVIEW_CHARS
    return TextPreviewOut(
        text=text[:MAX_PREVIEW_CHARS],
        truncated=truncated,
        available=bool(text.strip()),
    )


def _resolve_target(
    db: Session, actor: User, scope: str | None, municipality_id: uuid.UUID | None
) -> tuple[str, uuid.UUID | None]:
    """Where a new document lands, and whether this person may put it there.

    A municipality admin only ever writes to their own library — the parameter
    is ignored rather than rejected, so a stale form cannot post into somebody
    else's. A system admin chooses, and defaults to the shared library.
    """
    if actor.role != "system_admin":
        if actor.municipality_id is None:
            raise HTTPException(status_code=400, detail="no_municipality")
        return "municipality", actor.municipality_id

    if scope == "municipality":
        if municipality_id is None:
            raise HTTPException(status_code=400, detail="municipality_required")
        if db.get(Municipality, municipality_id) is None:
            raise HTTPException(status_code=404, detail="not_found")
        return "municipality", municipality_id
    return "global", None


@router.post("", status_code=201, response_model=KbDocOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    scope: str | None = Form(default=None),
    municipality_id: uuid.UUID | None = Form(default=None),
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> KbDocOut:
    doc_scope, muni_id = _resolve_target(db, actor, scope, municipality_id)
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
        municipality_id=muni_id,
        scope=doc_scope,
    )
    db.add(doc)
    db.flush()
    doc.storage_key = _storage_key(doc.id, filename)
    get_storage().put(doc.storage_key, content, content_type)
    _enqueue_doc(db, doc, ext)
    record_audit(
        db, actor_id=actor.id, action="kb_document.upload", entity_type="kb_document",
        entity_id=str(doc.id),
        after={"title": doc.title, "filename": filename, "scope": doc_scope},
    )
    db.commit()
    return _out(db, doc)


def _enqueue_doc(db: Session, doc: KbDocument, ext: str) -> None:
    """Index a document at its own scope.

    The visibility written onto every chunk is what the retrieval WHERE clause
    filters on, so a municipality's document must never be queued as global —
    that is the one mistake that would leak it to every other municipality.
    """
    enqueue(
        db,
        source_type="kb",
        source_id=doc.id,
        visibility=doc.scope,
        municipality_id=doc.municipality_id if doc.scope == "municipality" else None,
        storage_key=doc.storage_key,
        ext=ext,
        title=doc.title,
    )


@router.post("/{doc_id}/replace", response_model=KbDocOut)
async def replace_document(
    doc_id: uuid.UUID,
    file: UploadFile = File(...),
    actor: User = Depends(require_municipality_admin),
    db: Session = Depends(get_db),
) -> KbDocOut:
    doc = _get_or_404(db, doc_id, actor)
    _require_manager(doc, actor)
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
    _enqueue_doc(db, doc, ext)
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
    doc = _get_or_404(db, doc_id, actor)
    _require_manager(doc, actor)
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
    doc = _get_or_404(db, doc_id, actor)
    _require_manager(doc, actor)
    ext = doc.filename.rsplit(".", 1)[-1].lower()
    doc.status = "pending"
    doc.error = None
    _enqueue_doc(db, doc, ext)
    db.commit()
    return _out(db, doc)
