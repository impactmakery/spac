"""Turn retrieved chunks into user-facing citations that link to reachable sources."""

import uuid
from typing import TypedDict

from sqlalchemy.orm import Session

from app.models import (
    BoardComment,
    BoardItem,
    DepartmentFile,
    DepartmentPost,
    KbDocument,
)
from app.rag.retrieval import RetrievedChunk, source_numbers


class Citation(TypedDict):
    index: int
    title: str
    source_type: str
    source_id: str
    href: str


def build_citations(db: Session, chunks: list[RetrievedChunk]) -> list[Citation]:
    """One citation per distinct source, numbered exactly as the model sees them.

    The numbers come from source_numbers, the same function that labels the
    passages in the prompt — they have to agree, or every marker in every
    answer points somewhere other than where it says.
    """
    citations: list[Citation] = []
    seen: set[uuid.UUID] = set()
    for chunk, number in zip(chunks, source_numbers(chunks), strict=True):
        if chunk.source_id in seen:
            continue
        seen.add(chunk.source_id)
        title, href = _resolve(db, chunk)
        if title is None:
            # Source vanished between retrieval and render. Leave its number
            # unused rather than closing the gap: renumbering would move every
            # later citation out from under the markers already written.
            continue
        citations.append(
            Citation(
                index=number,
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
    if chunk.source_type == "comment":
        # A comment cites the post it belongs to: the post is where the reader
        # needs to land, and a comment has no page of its own.
        comment = db.get(BoardComment, chunk.source_id)
        if comment is None:
            return None, ""
        item = db.get(BoardItem, comment.item_id)
        return (item.title if item else None), f"/board/{comment.item_id}"
    if chunk.source_type == "department":
        file = db.get(DepartmentFile, chunk.source_id)
        if file is not None:
            return file.filename, f"/departments/{file.department_id}"
        post = db.get(DepartmentPost, chunk.source_id)
        if post is not None:
            excerpt = " ".join(post.body.split())[:60]
            return excerpt, f"/departments/{post.department_id}"
    return None, ""
