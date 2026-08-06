"""The graph is a second way to reach a chunk, so it is a second way to leak one.

Every test here exists because traversal crosses documents: a user may legitimately
see entity A, and A may be connected to B by an edge drawn from a document they
must never see. The filter has to hold on every hop, not only at the seed.
"""

import uuid

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    welfare = Department(municipality=m1, name="Welfare")
    education = Department(municipality=m1, name="Education")
    other_city = Department(municipality=m2, name="Health")
    pw = hash_password("graph-pass-1")
    db.add_all([
        m1, m2, welfare, education, other_city,
        User(email="sys@g.org", role="system_admin", status="active", password_hash=pw),
        User(email="welfare@g.org", role="department_user", municipality=m1,
             status="active", password_hash=pw, departments=[welfare]),
        User(email="edu@g.org", role="department_user", municipality=m1,
             status="active", password_hash=pw, departments=[education]),
        User(email="foreign@g.org", role="department_user", municipality=m2,
             status="active", password_hash=pw, departments=[other_city]),
    ])
    db.commit()
    return {
        "m1": m1, "m2": m2, "welfare": welfare, "education": education,
        "sys": db.query(User).filter_by(email="sys@g.org").one(),
        "welfare_user": db.query(User).filter_by(email="welfare@g.org").one(),
        "edu_user": db.query(User).filter_by(email="edu@g.org").one(),
        "foreign": db.query(User).filter_by(email="foreign@g.org").one(),
    }


def add_indexed_chunk(db, *, text, visibility, municipality=None, department=None):
    """Store a chunk and index it into the graph at the same scope."""
    from app.models import Chunk
    from app.rag.embeddings import get_embedding_provider
    from app.rag.graph import index_chunk

    chunk = Chunk(
        source_type="kb",
        source_id=uuid.uuid4(),
        visibility=visibility,
        municipality_id=municipality.id if municipality else None,
        department_id=department.id if department else None,
        content=text,
        embedding=get_embedding_provider().embed([text])[0],
    )
    db.add(chunk)
    db.flush()
    index_chunk(
        db,
        chunk_id=chunk.id,
        content=text,
        visibility=visibility,
        municipality_id=chunk.municipality_id,
        department_id=chunk.department_id,
    )
    db.commit()
    return chunk


# --- extraction --------------------------------------------------------------


def test_extractor_finds_the_references_municipal_documents_actually_carry():
    from app.rag.graph import get_extractor

    extraction = get_extractor().extract(
        "Applications use form 4B under regulation 17.3. "
        "The Department of Welfare reports to the Municipal Council."
    )
    names = {e.normalized for e in extraction.entities}
    assert any("regulation 17 3" == n or "regulation 17.3" in n for n in names)
    assert any("form 4b" in n for n in names)
    assert any(r.predicate == "reports to" for r in extraction.relations)


def test_normalisation_merges_spellings_without_merging_different_things():
    from app.rag.graph import normalize

    assert normalize("Department of Welfare") == normalize("department  of welfare")
    assert normalize("Regulation 17.3") == normalize("regulation 17 3")
    # a wrong merge invents a relationship no document states
    assert normalize("Department of Welfare") != normalize("Department of Education")


def test_extraction_is_stored_at_the_chunk_scope(db, world):
    from app.models import GraphMention

    chunk = add_indexed_chunk(
        db, text="The Department of Welfare manages the Intake Programme",
        visibility="department", municipality=world["m1"], department=world["welfare"],
    )
    mentions = db.query(GraphMention).filter_by(chunk_id=chunk.id).all()
    assert mentions
    assert all(m.visibility == "department" for m in mentions)
    assert all(m.department_id == world["welfare"].id for m in mentions)


# --- traversal and the permission boundary -----------------------------------


def test_traversal_finds_a_connection_across_two_documents(db, world):
    """The reason the graph exists: neither document alone answers the question."""
    from app.rag.graph import related_chunk_ids

    add_indexed_chunk(
        db, text="The Department of Welfare manages the Intake Programme",
        visibility="global",
    )
    add_indexed_chunk(
        db, text="The Intake Programme requires form 4B", visibility="global",
    )
    found = related_chunk_ids(
        db, query_text="Department of Welfare", user=world["welfare_user"]
    )
    assert len(found) >= 2, "traversal did not cross from one document to the other"


def test_traversal_cannot_step_into_an_edge_the_user_may_not_see(db, world):
    """The core risk: a permitted entity linked to a forbidden fact. The hop
    itself must be filtered, not just the starting point."""
    from app.rag.graph import related_chunk_ids

    # visible to everyone — this is the seed the user legitimately reaches
    add_indexed_chunk(
        db, text="The Department of Welfare manages the Intake Programme",
        visibility="global",
    )
    # the same entity, connected to something confidential in another department
    secret = add_indexed_chunk(
        db, text="The Intake Programme requires the Confidential Staffing Plan",
        visibility="department", municipality=world["m1"], department=world["education"],
    )

    reachable = related_chunk_ids(
        db, query_text="Department of Welfare", user=world["welfare_user"]
    )
    assert secret.id not in reachable

    # the department that owns it still reaches it
    owner_reachable = related_chunk_ids(
        db, query_text="Intake Programme", user=world["edu_user"]
    )
    assert secret.id in owner_reachable


def test_traversal_respects_municipality_boundaries(db, world):
    from app.rag.graph import related_chunk_ids

    internal = add_indexed_chunk(
        db, text="The Budget Committee approves the Capital Plan",
        visibility="municipality", municipality=world["m1"],
    )
    assert internal.id in related_chunk_ids(
        db, query_text="Budget Committee", user=world["welfare_user"]
    )
    assert internal.id not in related_chunk_ids(
        db, query_text="Budget Committee", user=world["foreign"]
    )


def test_archived_department_edges_are_unreachable(db, world):
    from app.rag.graph import related_chunk_ids

    chunk = add_indexed_chunk(
        db, text="The Legacy Unit manages the Old Programme",
        visibility="department", municipality=world["m1"], department=world["welfare"],
    )
    assert chunk.id in related_chunk_ids(
        db, query_text="Legacy Unit", user=world["welfare_user"]
    )

    world["welfare"].status = "archived"
    db.commit()
    assert related_chunk_ids(
        db, query_text="Legacy Unit", user=world["welfare_user"]
    ) == []


def test_system_admin_traverses_everything(db, world):
    from app.rag.graph import related_chunk_ids

    chunk = add_indexed_chunk(
        db, text="The Department of Welfare manages the Secret Programme",
        visibility="department", municipality=world["m1"], department=world["education"],
    )
    assert chunk.id in related_chunk_ids(
        db, query_text="Department of Welfare", user=world["sys"]
    )


def test_question_naming_nothing_known_returns_no_graph_signal(db, world):
    from app.rag.graph import related_chunk_ids

    add_indexed_chunk(db, text="The Department of Welfare manages Intake", visibility="global")
    assert related_chunk_ids(
        db, query_text="what is the weather like", user=world["welfare_user"]
    ) == []


def test_deleting_a_chunk_removes_its_graph_edges(db, world):
    """A deleted document must not stay traversable — the same invariant the
    chunks table already holds."""
    from sqlalchemy import delete

    from app.models import Chunk, GraphMention, GraphRelation

    chunk = add_indexed_chunk(
        db, text="The Department of Welfare manages the Intake Programme",
        visibility="global",
    )
    assert db.query(GraphMention).filter_by(chunk_id=chunk.id).count() > 0

    db.execute(delete(Chunk).where(Chunk.id == chunk.id))
    db.commit()

    assert db.query(GraphMention).filter_by(chunk_id=chunk.id).count() == 0
    assert db.query(GraphRelation).filter_by(chunk_id=chunk.id).count() == 0


# --- LLM extractor -----------------------------------------------------------
# It runs against free-tier models that rate-limit, so its failure modes matter
# as much as its happy path: a thin graph is acceptable, a failed ingestion is not.


class _StubLlm:
    """Stands in for the model, returning whatever a real one might."""

    def __init__(self, content):
        self.content = content
        self.calls = 0

    def __call__(self, body):
        self.calls += 1
        from app.rag.graph import LlmExtractor

        return LlmExtractor._parse(self.content)


def test_llm_extractor_parses_hebrew_entities_and_relations():
    from app.rag.graph import LlmExtractor

    extraction = LlmExtractor._parse('''
    {"entities": [{"name": "ועדת התקציב", "kind": "organization"},
                  {"name": "אגף הרווחה", "kind": "organization"},
                  {"name": "תוכנית רב-שנתית", "kind": "other"}],
     "relations": [{"subject": "ועדת התקציב", "predicate": "מאשרת", "object": "תוכנית רב-שנתית"},
                   {"subject": "תוכנית רב-שנתית", "predicate": "שייכת ל", "object": "אגף הרווחה"}]}
    ''')
    assert {e.name for e in extraction.entities} == {
        "ועדת התקציב", "אגף הרווחה", "תוכנית רב-שנתית"
    }
    # the relationships the pattern extractor cannot find in Hebrew
    assert len(extraction.relations) == 2
    assert ("ועדת התקציב", "מאשרת") == (
        extraction.relations[0].subject, extraction.relations[0].predicate
    )


def test_llm_extractor_survives_a_fenced_or_chatty_response():
    """Models wrap JSON in fences and preamble however firmly you ask them not to."""
    from app.rag.graph import LlmExtractor

    extraction = LlmExtractor._parse(
        'Sure! Here is the graph:\n```json\n'
        '{"entities": [{"name": "Budget Committee", "kind": "organization"}], "relations": []}\n'
        '```\nLet me know if you need anything else.'
    )
    assert [e.name for e in extraction.entities] == ["Budget Committee"]


def test_llm_extractor_drops_relations_whose_ends_were_never_declared():
    """A dangling relation would create an edge to an entity that does not
    exist — a connection the document never stated."""
    from app.rag.graph import LlmExtractor

    extraction = LlmExtractor._parse('''
    {"entities": [{"name": "אגף הרווחה", "kind": "organization"}],
     "relations": [{"subject": "אגף הרווחה", "predicate": "מנהל", "object": "משהו שלא הוזכר"}]}
    ''')
    assert extraction.relations == []


def test_llm_extractor_falls_back_when_the_provider_fails():
    """A rate-limited provider must thin the graph, never fail ingestion."""
    from app.rag.graph import LlmExtractor

    extractor = LlmExtractor()
    extractor._call = lambda body: (_ for _ in ()).throw(RuntimeError("429 rate limited"))

    extraction = extractor.extract("Budget Committee approves the Capital Plan")
    # the pattern extractor still finds something rather than raising
    assert any("budget committee" == e.normalized for e in extraction.entities)


def test_llm_extractor_falls_back_when_no_key_is_configured():
    from app.rag.graph import LlmExtractor

    extractor = LlmExtractor()
    extractor._call = lambda body: None
    extraction = extractor.extract("Budget Committee approves the Capital Plan")
    assert extraction.entities


def test_malformed_json_falls_back_rather_than_raising():
    from app.rag.graph import LlmExtractor

    extractor = LlmExtractor()
    extractor._call = lambda body: LlmExtractor._parse("this is not json at all")
    assert extractor.extract("Budget Committee approves the Capital Plan").entities


def test_pattern_extractor_is_the_default(monkeypatch):
    """Nobody should start paying per chunk by accident."""
    from app.rag.graph import PatternExtractor, get_extractor, set_extractor

    set_extractor(None)  # re-read configuration
    try:
        assert isinstance(get_extractor(), PatternExtractor)
    finally:
        set_extractor(None)


def test_seeding_matches_an_entity_named_inside_a_longer_question(db, world):
    """Questions are not entity lists. "מה התקציב של אגף הרווחה?" must still seed
    on אגף הרווחה — and finding seeds must not require running an extractor on
    the question, which with the LLM extractor would be a model call per answer."""
    from app.rag.graph import related_chunk_ids

    chunk = add_indexed_chunk(
        db, text="אגף הרווחה מנהל את תוכנית הקליטה", visibility="global",
    )
    found = related_chunk_ids(
        db, query_text="מה התקציב השנתי של אגף הרווחה בשנת 2026?",
        user=world["welfare_user"],
    )
    assert chunk.id in found


def test_seeding_does_not_require_the_extractor(db, world, monkeypatch):
    from app.rag import graph as graph_mod

    add_indexed_chunk(db, text="Budget Committee approves the Capital Plan",
                      visibility="global")

    def explode(_body):
        raise AssertionError("the extractor must not run on the query path")

    class Exploding:
        extract = staticmethod(explode)

    graph_mod.set_extractor(Exploding())
    try:
        assert graph_mod.related_chunk_ids(
            db, query_text="who approves the Capital Plan",
            user=world["welfare_user"],
        )
    finally:
        graph_mod.set_extractor(None)


def test_very_short_questions_seed_nothing(db, world):
    from app.rag.graph import related_chunk_ids

    add_indexed_chunk(db, text="Budget Committee approves the Capital Plan",
                      visibility="global")
    assert related_chunk_ids(db, query_text="hi", user=world["welfare_user"]) == []
