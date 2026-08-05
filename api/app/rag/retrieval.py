"""Permission-filtered retrieval.

The permission predicate is part of the SQL — never a post-filter. A user must
never receive an answer sourced from content they cannot see.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User

TOP_K = 12
MIN_SIMILARITY = 0.35

# Cosine similarity = 1 - cosine distance (pgvector's <=> operator).
RETRIEVAL_SQL = """
SELECT c.id, c.source_type, c.source_id, c.content, c.visibility,
       c.municipality_id, c.department_id,
       1 - (c.embedding <=> CAST(:query_embedding AS vector)) AS similarity
FROM chunks c
LEFT JOIN municipalities m ON m.id = c.municipality_id
LEFT JOIN departments d ON d.id = c.department_id
WHERE
    (m.id IS NULL OR m.status = 'active')
    AND (d.id IS NULL OR d.status = 'active')
    AND (
        :is_system_admin
        OR c.visibility = 'global'
        OR (c.visibility = 'municipality' AND c.municipality_id = :user_municipality_id)
        OR (c.visibility = 'department' AND c.department_id = ANY(:user_department_ids))
    )
    AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
LIMIT :top_k
"""


@dataclass(frozen=True)
class RetrievedChunk:
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    content: str
    visibility: str
    municipality_id: uuid.UUID | None
    department_id: uuid.UUID | None
    similarity: float


def retrieve(
    db: Session,
    *,
    query_embedding: list[float],
    user: User,
    limit: int = TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> list[RetrievedChunk]:
    params = {
        "query_embedding": "[" + ",".join(str(x) for x in query_embedding) + "]",
        "is_system_admin": user.role == "system_admin",
        "user_municipality_id": user.municipality_id,
        "user_department_ids": [
            d.id for d in user.departments if d.status == "active"
        ] or [uuid.UUID(int=0)],
        "min_similarity": min_similarity,
        "top_k": limit,
    }
    rows = db.execute(text(RETRIEVAL_SQL), params).mappings().all()
    return [
        RetrievedChunk(
            id=r["id"],
            source_type=r["source_type"],
            source_id=r["source_id"],
            content=r["content"],
            visibility=r["visibility"],
            municipality_id=r["municipality_id"],
            department_id=r["department_id"],
            similarity=float(r["similarity"]),
        )
        for r in rows
    ]
