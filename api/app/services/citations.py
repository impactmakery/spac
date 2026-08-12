"""Turn retrieved chunks into user-facing citations that link to reachable sources."""

import re
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


# [1] or [12]; the prompt asks for one marker each, never [1, 2].
_MARKER = re.compile(r"\[(\d{1,2})\]")


def cited_in(answer: str, citations: list[Citation]) -> list[Citation]:
    """The sources the answer actually used, in the order it used them.

    Retrieval reads more than the answer needs: a question about one document
    routinely pulls passages from three or four that share vocabulary. Listing
    all of them says the answer rests on four documents when it rests on one,
    and someone checking the third finds no sentence it supports — in a product
    whose promise is that every claim can be verified.

    An answer citing nothing keeps the full list. That happens when the model
    ignores the instruction, and showing what was read beats showing nothing at
    all.
    """
    used = [int(m) for m in _MARKER.findall(answer)]
    if not used:
        return citations
    # dict keys keep insertion order and drop repeats: a source cited three
    # times is listed once, where it was first relied on.
    first_use = dict.fromkeys(used)
    by_index = {c["index"]: c for c in citations}
    return [by_index[n] for n in first_use if n in by_index]
