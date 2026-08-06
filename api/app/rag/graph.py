"""Knowledge graph: entities and the relationships between them.

Vector and lexical search both answer "which passage looks like this question".
Neither answers "which department runs that programme", "what does this
regulation depend on", or "who signed both of these" — questions about
*connections*, where the answer is assembled from several documents that share
an entity rather than found in one passage.

Permission model, which is the whole risk of adding this:

    scope lives on the MENTION and the RELATION, never on the ENTITY.

An entity is only a name. "אגף הרווחה" may appear in a global circular and in a
confidential department file; those are two facts with different visibility.
Scoping the entity would merge them, and a traversal starting from a permitted
mention could then walk into a relationship the user must not see. Every edge
therefore carries the visibility of the chunk that evidenced it, and traversal
re-applies the same predicate the retrieval SQL uses — on every hop, not once at
the start.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User

log = logging.getLogger(__name__)

# Hops beyond two rarely add signal and multiply the rows scanned; two is enough
# for "A relates to B, and B relates to the thing you asked about".
MAX_HOPS = 2
MAX_SEED_ENTITIES = 8
MAX_GRAPH_CHUNKS = 20

KINDS = ("person", "organization", "location", "regulation", "date", "other")


@dataclass(frozen=True)
class Entity:
    name: str
    kind: str = "other"

    @property
    def normalized(self) -> str:
        return normalize(self.name)


@dataclass(frozen=True)
class Relation:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0


@dataclass
class Extraction:
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


def normalize(name: str) -> str:
    """Collapse spellings that should be the same node.

    Deliberately conservative: it lowercases, strips punctuation and collapses
    whitespace, but does not stem or transliterate. Merging two entities that
    are not the same thing is worse than keeping duplicates — a wrong merge
    invents a relationship that no document states.
    """
    cleaned = re.sub(r"[^\w\s]", " ", name, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    # "The Department of Welfare" and "Department of Welfare" are one thing. Left
    # alone they become two nodes, and a question naming one would not reach an
    # edge stored under the other.
    #
    # English articles only. Hebrew marks the definite article with a prefixed ה
    # on the word itself, and stripping that would merge genuinely different
    # words — the conservative rule above applies.
    return re.sub(r"^(?:the|a|an)\s+", "", cleaned)


class Extractor(Protocol):
    def extract(self, text: str) -> Extraction: ...


class PatternExtractor:
    """Deterministic, offline, free.

    Finds the entity shapes that actually carry weight in municipal documents —
    regulation and form references, dates, and capitalised or Hebrew proper
    names — and the relationships stated by a small set of explicit verbs.

    It will not match an LLM's recall. It exists so the graph works with no API
    key, so tests are hermetic, and so a rate-limited provider degrades the graph
    rather than breaking ingestion.
    """

    # "regulation 17.3", "form 4B", "תקנה 12", "טופס 4ב"
    _REFERENCE = re.compile(
        r"\b(?:regulation|form|section|clause|תקנה|טופס|סעיף|נוהל)\s+[\w./֐-׿-]+",
        re.IGNORECASE | re.UNICODE,
    )
    # Two or more capitalised words, or a Hebrew multi-word proper name.
    # Each continuation must consume its own separator: a pattern that only
    # eats the space inside "of"/"and" matches "Department of Welfare" but
    # silently misses "Budget Committee", which is the more common shape.
    _PROPER = re.compile(
        r"\b[A-Z][\w'-]+(?:\s+(?:of|the|and|for)\s+[A-Z][\w'-]+|\s+[A-Z][\w'-]+)+|"
        r"(?:[֐-׿]{2,}\s+){1,3}[֐-׿]{2,}",
        re.UNICODE,
    )
    _DATE = re.compile(
        r"\b(?:\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December|ינואר|פברואר|מרץ|אפריל|מאי|יוני|"
        r"יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)\s*\d{0,4}\b",
        re.IGNORECASE | re.UNICODE,
    )
    _ORG_HINT = re.compile(
        r"(department|municipality|office|committee|council|אגף|עירייה|מחלקה|ועדה|מועצה)",
        re.IGNORECASE | re.UNICODE,
    )

    # subject <verb> object, where the verb states a relationship worth storing
    _RELATION = re.compile(
        r"(?P<subject>[\w֐-׿][\w\s֐-׿'-]{2,60}?)\s+"
        r"(?P<predicate>requires|reports to|belongs to|manages|operates|approves|"
        r"replaces|amends|is responsible for|מנהל|אחראי על|כפוף ל|מחליף|מאשר)\s+"
        r"(?P<object>[\w֐-׿][\w\s֐-׿'-]{2,60})",
        re.IGNORECASE | re.UNICODE,
    )

    # Hebrew has no capitalisation, so a "run of Hebrew words" pattern happily
    # swallows the verb and its object: "אגף הרווחה מנהל את תוכנית" comes back as
    # one entity. Cutting the span at a function word recovers the noun phrase.
    _HEBREW_STOP = frozenset(
        "את של על אל מן עם אך גם או זה זו היא הוא אשר כי לא כל יש אין אם כאשר "
        "לפי בין תחת אחרי לפני מול כדי אצל".split()
    )

    def _trim_hebrew(self, phrase: str) -> str:
        words = phrase.split()
        kept: list[str] = []
        for word in words:
            if word in self._HEBREW_STOP:
                break
            kept.append(word)
        while kept and kept[-1] in self._HEBREW_STOP:
            kept.pop()
        return " ".join(kept)

    def extract(self, body: str) -> Extraction:
        seen: dict[str, Entity] = {}

        def add(name: str, kind: str) -> None:
            name = name.strip(" \t\n.,;:")
            if any("֐" <= ch <= "׿" for ch in name):
                name = self._trim_hebrew(name)
            if len(name) < 3 or len(name) > 120:
                return
            key = normalize(name)
            if key and key not in seen:
                seen[key] = Entity(name=name, kind=kind)

        for match in self._REFERENCE.finditer(body):
            add(match.group(0), "regulation")
        for match in self._DATE.finditer(body):
            add(match.group(0), "date")
        for match in self._PROPER.finditer(body):
            phrase = match.group(0)
            add(phrase, "organization" if self._ORG_HINT.search(phrase) else "other")

        relations = []
        for match in self._RELATION.finditer(body):
            subject = match.group("subject").strip()
            obj = match.group("object").strip()
            if normalize(subject) == normalize(obj):
                continue
            add(subject, "other")
            add(obj, "other")
            relations.append(
                Relation(
                    subject=subject,
                    predicate=match.group("predicate").lower().strip(),
                    object=obj,
                    confidence=0.6,  # a pattern match is weaker evidence than a model's
                )
            )

        return Extraction(entities=list(seen.values()), relations=relations)


EXTRACTION_PROMPT = """You extract a knowledge graph from municipal documents.

Return ONLY a JSON object, no prose and no code fence:
{"entities": [{"name": "...", "kind": "..."}],
 "relations": [{"subject": "...", "predicate": "...", "object": "..."}]}

kind is one of: person, organization, location, regulation, date, other.

Rules:
- Keep names exactly as they appear in the text. Do not translate them. A Hebrew
  document must yield Hebrew entity names.
- Only extract relationships the text actually states. Never infer, never use
  outside knowledge. A relationship you invent becomes an answer the document
  does not support.
- Every subject and object of a relation must also appear in entities.
- Prefer specific named things (אגף הרווחה, ועדת התקציב, תקנה 17.3) over generic
  nouns (the department, the committee, the regulation).
- Predicates should be short verb phrases in the document's own language.
- If the text names nothing worth linking, return empty lists."""

MAX_EXTRACTION_CHARS = 6000


class LlmExtractor:
    """Reads the chunk and reports what is named and how it connects.

    This is what makes the graph useful in Hebrew. Pattern matching leans on
    capitalisation, which Hebrew does not have, so it finds some entities and
    almost no relationships — and relationships are the whole point of a graph.

    Costs one model call per chunk at index time, paid once per document rather
    than once per question. Falls back to the pattern extractor on any failure:
    a rate-limited provider should thin the graph, never fail an ingestion job.
    """

    def __init__(self, fallback: Extractor | None = None) -> None:
        self._fallback = fallback or PatternExtractor()

    def extract(self, body: str) -> Extraction:
        try:
            parsed = self._call(body[:MAX_EXTRACTION_CHARS])
        except Exception as e:  # noqa: BLE001
            log.warning("LLM extraction failed, falling back to patterns: %s", e)
            return self._fallback.extract(body)
        if parsed is None:
            return self._fallback.extract(body)
        return parsed

    def _call(self, body: str) -> Extraction | None:
        from openai import OpenAI

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.resolved_llm_key:
            return None

        headers = {}
        if settings.resolved_llm_base_url and "openrouter" in settings.resolved_llm_base_url:
            headers = {
                "HTTP-Referer": settings.openrouter_site_url or settings.nextauth_url,
                "X-Title": settings.openrouter_app_name,
            }
        client = OpenAI(
            api_key=settings.resolved_llm_key,
            base_url=settings.resolved_llm_base_url,
            default_headers=headers or None,
        )

        last_error: Exception | None = None
        for model in settings.llm_model_chain:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_PROMPT},
                        {"role": "user", "content": body},
                    ],
                    temperature=0,  # extraction is not a creative task
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return self._parse(content)
            except Exception as e:  # noqa: BLE001 — try the next model in the chain
                last_error = e
                continue
        if last_error:
            raise last_error
        return None

    @staticmethod
    def _parse(content: str) -> Extraction:
        import json
        import re as _re

        # Models wrap JSON in fences or prose no matter how firmly you ask.
        fenced = _re.search(r"```(?:json)?\s*(.+?)```", content, _re.DOTALL)
        if fenced:
            content = fenced.group(1)
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object in extraction response")
        data = json.loads(content[start : end + 1])

        entities = []
        for item in data.get("entities", []):
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            kind = str(item.get("kind", "other")).lower()
            entities.append(Entity(name=name, kind=kind if kind in KINDS else "other"))

        known = {e.normalized for e in entities}
        relations = []
        for item in data.get("relations", []):
            subject = str(item.get("subject", "")).strip()
            predicate = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()
            if not (subject and predicate and obj):
                continue
            # A relation whose ends were not also declared as entities would
            # dangle; the model is told to declare them, and this enforces it.
            if normalize(subject) not in known or normalize(obj) not in known:
                continue
            if normalize(subject) == normalize(obj):
                continue
            relations.append(Relation(subject=subject, predicate=predicate, object=obj))

        return Extraction(entities=entities, relations=relations)


_extractor: Extractor | None = None


def get_extractor() -> Extractor:
    """The LLM extractor when a key and GRAPH_EXTRACTOR=llm are both present.

    Off by default even with a key configured: it adds a model call per chunk,
    and that is a cost decision the operator should make deliberately rather
    than discover on a bill.
    """
    global _extractor
    if _extractor is None:
        from app.core.config import get_settings

        settings = get_settings()
        if settings.graph_extractor == "llm" and settings.resolved_llm_key:
            _extractor = LlmExtractor()
        else:
            _extractor = PatternExtractor()
    return _extractor


def set_extractor(extractor: Extractor | None) -> None:
    """Override the extractor, or pass None to re-read the configuration."""
    global _extractor
    _extractor = extractor


# --- storage -----------------------------------------------------------------


def upsert_entity(db: Session, entity: Entity) -> uuid.UUID:
    from app.models import GraphEntity

    key = entity.normalized
    existing = db.scalar(
        text("SELECT id FROM graph_entities WHERE normalized = :n").bindparams(n=key)
    )
    if existing:
        return existing
    row = GraphEntity(
        name=entity.name,
        normalized=key,
        kind=entity.kind if entity.kind in KINDS else "other",
    )
    db.add(row)
    db.flush()
    return row.id


def index_chunk(
    db: Session,
    *,
    chunk_id: uuid.UUID,
    content: str,
    visibility: str,
    municipality_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
) -> tuple[int, int]:
    """Extract from one chunk and store mentions and relations at its scope.

    Returns (entities, relations) written. Caller owns the transaction.
    """
    from app.models import GraphMention, GraphRelation

    extraction = get_extractor().extract(content)
    ids: dict[str, uuid.UUID] = {}

    for entity in extraction.entities:
        entity_id = upsert_entity(db, entity)
        ids[entity.normalized] = entity_id
        db.add(
            GraphMention(
                entity_id=entity_id,
                chunk_id=chunk_id,
                municipality_id=municipality_id,
                department_id=department_id,
                visibility=visibility,
            )
        )

    written = 0
    for relation in extraction.relations:
        subject_id = ids.get(normalize(relation.subject))
        object_id = ids.get(normalize(relation.object))
        if not subject_id or not object_id or subject_id == object_id:
            continue
        db.add(
            GraphRelation(
                subject_id=subject_id,
                object_id=object_id,
                predicate=relation.predicate,
                chunk_id=chunk_id,
                municipality_id=municipality_id,
                department_id=department_id,
                visibility=visibility,
                confidence=relation.confidence,
            )
        )
        written += 1

    return len(extraction.entities), written


# --- traversal ---------------------------------------------------------------
# The predicate is the same shape retrieval uses, applied to the edge's own
# scope columns. It is interpolated into every hop.

_EDGE_PERMISSION = """
    (
        :is_system_admin
        OR e.visibility = 'global'
        OR (e.visibility = 'municipality' AND e.municipality_id = :user_municipality_id)
        OR (e.visibility = 'department' AND e.department_id = ANY(:user_department_ids))
    )
"""

SEED_SQL = f"""
SELECT DISTINCT ge.id, ge.name
FROM graph_entities ge
JOIN graph_mentions e ON e.entity_id = ge.id
LEFT JOIN municipalities m ON m.id = e.municipality_id
LEFT JOIN departments d ON d.id = e.department_id
WHERE ge.normalized = ANY(:names)
  AND (m.id IS NULL OR m.status = 'active')
  AND (d.id IS NULL OR d.status = 'active')
  AND {_EDGE_PERMISSION}
LIMIT :max_seeds
"""

# Walks outward from the seeds, re-applying the filter on every hop, then
# returns the chunks that evidenced the edges it was allowed to cross.
TRAVERSE_SQL = f"""
WITH RECURSIVE reachable(entity_id, depth) AS (
    SELECT unnest(CAST(:seed_ids AS uuid[])), 0
  UNION
    SELECT CASE WHEN e.subject_id = r.entity_id THEN e.object_id ELSE e.subject_id END,
           r.depth + 1
    FROM reachable r
    JOIN graph_relations e
      ON (e.subject_id = r.entity_id OR e.object_id = r.entity_id)
    LEFT JOIN municipalities m ON m.id = e.municipality_id
    LEFT JOIN departments d ON d.id = e.department_id
    WHERE r.depth < :max_hops
      AND (m.id IS NULL OR m.status = 'active')
      AND (d.id IS NULL OR d.status = 'active')
      AND {_EDGE_PERMISSION}
)
SELECT DISTINCT e.chunk_id
FROM reachable r
JOIN graph_relations e
  ON (e.subject_id = r.entity_id OR e.object_id = r.entity_id)
LEFT JOIN municipalities m ON m.id = e.municipality_id
LEFT JOIN departments d ON d.id = e.department_id
WHERE (m.id IS NULL OR m.status = 'active')
  AND (d.id IS NULL OR d.status = 'active')
  AND {_EDGE_PERMISSION}
LIMIT :max_chunks
"""


def _permission_params(user: User) -> dict:
    return {
        "is_system_admin": user.role == "system_admin",
        "user_municipality_id": user.municipality_id,
        "user_department_ids": [
            d.id for d in user.departments if d.status == "active"
        ] or [uuid.UUID(int=0)],
    }


def related_chunk_ids(
    db: Session, *, query_text: str, user: User, max_hops: int = MAX_HOPS
) -> list[uuid.UUID]:
    """Chunk ids reachable from the entities named in the question.

    Returns only chunks whose evidencing edges this user may see at every hop.
    An empty list is the normal answer for a question that names nothing the
    graph knows about, and callers must treat it as "no graph signal" rather
    than "no results".
    """
    extraction = get_extractor().extract(query_text)
    names = [e.normalized for e in extraction.entities]
    if not names:
        return []

    params = _permission_params(user)
    seeds = db.execute(
        text(SEED_SQL), {**params, "names": names, "max_seeds": MAX_SEED_ENTITIES}
    ).all()
    if not seeds:
        return []

    rows = db.execute(
        text(TRAVERSE_SQL),
        {
            **params,
            "seed_ids": [str(s.id) for s in seeds],
            "max_hops": max_hops,
            "max_chunks": MAX_GRAPH_CHUNKS,
        },
    ).all()
    return [r.chunk_id for r in rows]
