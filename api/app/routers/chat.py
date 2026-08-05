import json
import uuid
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_db
from app.core.ratelimit import RateLimiter
from app.core.security import get_current_user
from app.models import (
    Conversation,
    KbDocument,
    Message,
    MessageDebug,
    UnansweredQuestion,
    User,
)
from app.rag.embeddings import get_embedding_provider
from app.rag.generation import (
    HISTORY_EXCHANGES,
    build_prompt,
    not_covered_reply,
    stream_answer,
)
from app.rag.retrieval import RETRIEVAL_SQL, retrieve
from app.services.citations import build_citations

router = APIRouter(prefix="/api", tags=["chat"])

MESSAGE_PAGE = 50
chat_limiter = RateLimiter(60, 3600)  # 60 messages per hour per user


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list | None
    created_at: datetime


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _own_conversation_or_404(
    db: Session, conversation_id: uuid.UUID, user: User
) -> Conversation:
    convo = db.get(Conversation, conversation_id)
    # private even from the system admin (scope appendix)
    if convo is None or convo.user_id != user.id:
        raise HTTPException(status_code=404, detail="not_found")
    return convo


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ConversationOut]:
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.updated_at))
    ).all()
    return [
        ConversationOut(
            id=str(c.id), title=c.title, created_at=c.created_at, updated_at=c.updated_at
        )
        for c in rows
    ]


@router.post("/conversations", status_code=201, response_model=ConversationOut)
def create_conversation(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConversationOut:
    convo = Conversation(user_id=user.id)
    db.add(convo)
    db.commit()
    return ConversationOut(
        id=str(convo.id),
        title=convo.title,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
    )


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: uuid.UUID,
    body: ConversationPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    convo = _own_conversation_or_404(db, conversation_id, user)
    convo.title = body.title
    db.commit()
    return ConversationOut(
        id=str(convo.id),
        title=convo.title,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
    )


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    convo = _own_conversation_or_404(db, conversation_id, user)
    db.delete(convo)
    db.commit()
    return {"ok": True}


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageOut]
)
def list_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    _own_conversation_or_404(db, conversation_id, user)
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(MESSAGE_PAGE)
    ).all()
    return [
        MessageOut(
            id=str(m.id),
            role=m.role,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at,
        )
        for m in reversed(rows)
    ]


@router.get("/chat/sample-questions", response_model=list[str])
def sample_questions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[str]:
    """Four starter questions drawn from knowledge base document titles."""
    titles = db.scalars(
        select(KbDocument.title).order_by(desc(KbDocument.created_at)).limit(4)
    ).all()
    if user.language == "he":
        return [f"מה כתוב במסמך «{t}»?" for t in titles]
    return [f"What does the document “{t}” say?" for t in titles]


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/{conversation_id}/messages")
def send_message(
    conversation_id: uuid.UUID,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    convo = _own_conversation_or_404(db, conversation_id, user)
    if not chat_limiter.hit(str(user.id)):
        raise HTTPException(status_code=429, detail="rate_limited")

    question = body.content.strip()
    user_message = Message(conversation_id=convo.id, role="user", content=question)
    db.add(user_message)
    if not convo.title:
        convo.title = question[:80]
    db.commit()

    history = [
        (m.role, m.content)
        for m in db.scalars(
            select(Message)
            .where(Message.conversation_id == convo.id, Message.id != user_message.id)
            .order_by(desc(Message.created_at))
            .limit(HISTORY_EXCHANGES * 2)
        ).all()
    ][::-1]

    [query_embedding] = get_embedding_provider().embed([question])
    chunks = retrieve(db, query_embedding=query_embedding, user=user)
    citations = build_citations(db, chunks) if chunks else []
    # a citation-less answer must be impossible: without reachable sources we
    # return the standard not-covered reply instead of generating.
    if not citations:
        chunks = []

    user_id = user.id
    municipality_id = user.municipality_id
    conversation_id_val = convo.id
    prompt = build_prompt(question, chunks, history) if chunks else ""
    chunk_ids = [str(c.id) for c in chunks]
    scores = [round(c.similarity, 4) for c in chunks]

    def event_stream() -> Iterator[str]:
        pieces: list[str] = []
        if chunks:
            for token in stream_answer(question, chunks, history):
                pieces.append(token)
                yield _sse("token", token)
            answer = "".join(pieces)
        else:
            answer = not_covered_reply(question)
            yield _sse("token", answer)

        yield _sse("citations", citations)

        # persist on a fresh session: the request session closes with the response
        engine_session = sessionmaker(
            bind=db.get_bind(), expire_on_commit=False
        )
        with engine_session() as write_db:
            assistant = Message(
                conversation_id=conversation_id_val,
                role="assistant",
                content=answer,
                citations=citations or None,
            )
            write_db.add(assistant)
            write_db.flush()
            write_db.add(
                MessageDebug(
                    message_id=assistant.id,
                    retrieval_sql=RETRIEVAL_SQL,
                    chunk_ids=chunk_ids,
                    scores=scores,
                    prompt=prompt or None,
                )
            )
            if not chunks:
                write_db.add(
                    UnansweredQuestion(
                        user_id=user_id,
                        municipality_id=municipality_id,
                        question=question,
                    )
                )
            write_db.commit()
            yield _sse("done", {"message_id": str(assistant.id)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
