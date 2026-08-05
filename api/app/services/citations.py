"""Turn retrieved chunks into user-facing citations that link to reachable sources."""

import uuid
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models import BoardItem, DepartmentFile, DepartmentPost, KbDocument
from app.rag.retrieval import RetrievedChunk


class Citation(TypedDict):
    index: int
    title: str
    source_type: str
    source_id: str
    href: str


def build_citations(db: Session, chunks: list[RetrievedChunk]) -> list[Citation]:
    """One citation per distinct source, numbered in the order the model sees them."""
    citations: list[Citation] = []
    seen: dict[uuid.UUID, int] = {}
    for i, chunk in enumerate(chunks):
        if chunk.source_id in seen:
            continue
        title, href = _resolve(db, chunk)
        if title is None:
            continue  # source vanished (deleted between retrieval and render)
        seen[chunk.source_id] = i
        citations.append(
            Citation(
                index=len(citations) + 1,
                title=title,
                source_type=chunk.source_type,
                source_id=str(chunk.source_id),
                href=href,
            )
        )
    return citations


def _resolve(db: Session, chunk: RetrievedChunk) -> tuple[str | None, str]:
    if chunk.source_type == "kb":
        doc = db.get(KbDocument, chunk.source_id)
        return (doc.title if doc else None), f"/knowledge/{chunk.source_id}"
    if chunk.source_type == "board":
        item = db.get(BoardItem, chunk.source_id)
        return (item.title if item else None), f"/board/{chunk.source_id}"
    if chunk.source_type == "department":
        file = db.get(DepartmentFile, chunk.source_id)
        if file is not None:
            return file.filename, f"/departments/{file.department_id}"
        post = db.get(DepartmentPost, chunk.source_id)
        if post is not None:
            excerpt = " ".join(post.body.split())[:60]
            return excerpt, f"/departments/{post.department_id}"
    return None, ""
