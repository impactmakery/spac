"""Permission-filtered hybrid retrieval.

Two independent searches over the same rows — dense vectors for meaning, Postgres
full-text for exact tokens — fused with Reciprocal Rank Fusion. Dense retrieval
alone misses the things municipal staff actually search for: form numbers,
regulation references, department names. Lexical alone misses paraphrase.

The permission predicate is part of BOTH arms and of the final select. It is
never a post-filter, and a new retrieval path must never become a way around it.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User

TOP_K = 12
MIN_SIMILARITY = 0.35
CANDIDATES = 40  # per arm, before fusion
RRF_K = 60  # standard damping: rank 1 scores 1/61, rank 2 1/62, …

# The predicate is written once and interpolated into both arms so they can
# never drift apart.
_PERMISSION = """
    (m.id IS NULL OR m.status = 'active')
    AND (d.id IS NULL OR d.status = 'active')
    AND (
        :is_system_admin
        OR c.visibility = 'global'
        OR (c.visibility = 'municipality' AND c.municipality_id = :user_municipality_id)
        OR (c.visibility = 'department' AND c.department_id = ANY(:user_department_ids))
    )
"""

RETRIEVAL_SQL = f"""
WITH q AS (
    -- OR rather than AND: plainto_tsquery ANDs every word, so a natural
    -- question would only match a document containing all of them. Rewriting
    -- the operators keeps Postgres's own sanitisation of the raw input.
    SELECT tsq, qarr, cardinality(qarr) AS qn
    FROM (
        SELECT NULLIF(
                   replace(plainto_tsquery('english', :query_text)::text, '&', '|'), ''
               )::tsquery AS tsq,
               tsvector_to_array(to_tsvector('english', :query_text)) AS qarr
    ) parsed
),
dense AS (
    SELECT c.id,
           1 - (c.embedding <=> CAST(:query_embedding AS vector)) AS similarity,
           ROW_NUMBER() OVER (
               ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
           ) AS rank
    FROM chunks c
    LEFT JOIN municipalities m ON m.id = c.municipality_id
    LEFT JOIN departments d ON d.id = c.department_id
    WHERE {_PERMISSION}
      AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
    ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :candidates
),
lexical AS (
    SELECT c.id,
           ts_rank_cd(c.search, q.tsq) AS lex_score,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.search, q.tsq) DESC) AS rank
    FROM chunks c
    CROSS JOIN q
    LEFT JOIN municipalities m ON m.id = c.municipality_id
    LEFT JOIN departments d ON d.id = c.department_id
    WHERE {_PERMISSION}
      AND q.tsq IS NOT NULL
      AND c.search @@ q.tsq
      -- OR-ing the terms buys recall but would otherwise let a chunk in on one
      -- incidental word ("plan"), and an unanswerable question would come back
      -- with confident-looking citations. Demand most of the question's content
      -- words, so lexical recall means real evidence — while a short, precise
      -- query ("regulation 17.3") still needs only its own terms.
      AND (
          SELECT count(*)
          FROM unnest(q.qarr) AS lexeme
          WHERE lexeme = ANY(tsvector_to_array(c.search))
      ) >= LEAST(q.qn, GREATEST(2, CEIL(0.6 * q.qn)))
    ORDER BY ts_rank_cd(c.search, q.tsq) DESC
    LIMIT :candidates
),
fused AS (
    SELECT COALESCE(dense.id, lexical.id) AS id,
           COALESCE(1.0 / (:rrf_k + dense.rank), 0)
             + COALESCE(1.0 / (:rrf_k + lexical.rank), 0) AS score,
           COALESCE(dense.similarity, 0) AS similarity,
           dense.id IS NOT NULL AS from_dense,
           lexical.id IS NOT NULL AS from_lexical
    FROM dense
    FULL OUTER JOIN lexical ON dense.id = lexical.id
)
SELECT c.id, c.source_type, c.source_id, c.content, c.visibility,
       c.municipality_id, c.department_id,
       fused.similarity, fused.score, fused.from_dense, fused.from_lexical
FROM fused
JOIN chunks c ON c.id = fused.id
LEFT JOIN municipalities m ON m.id = c.municipality_id
LEFT JOIN departments d ON d.id = c.department_id
WHERE {_PERMISSION}
ORDER BY fused.score DESC, fused.similarity DESC
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
    score: float = 0.0
    from_dense: bool = True
    from_lexical: bool = False


def retrieve(
    db: Session,
    *,
    query_embedding: list[float],
    user: User,
    query_text: str = "",
    limit: int = TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> list[RetrievedChunk]:
    params = {
        "query_embedding": "[" + ",".join(str(x) for x in query_embedding) + "]",
        "query_text": query_text,
        "is_system_admin": user.role == "system_admin",
        "user_municipality_id": user.municipality_id,
        "user_department_ids": [
            d.id for d in user.departments if d.status == "active"
        ] or [uuid.UUID(int=0)],
        "min_similarity": min_similarity,
        "candidates": CANDIDATES,
        "rrf_k": RRF_K,
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
            score=float(r["score"]),
            from_dense=bool(r["from_dense"]),
            from_lexical=bool(r["from_lexical"]),
        )
        for r in rows
    ]
