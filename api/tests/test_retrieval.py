"""The permission boundary of the whole product: retrieval must never return a
chunk the asking user cannot see. The filter lives inside the SQL."""

import uuid

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    d1b = Department(municipality=m1, name="Education")
    d2 = Department(municipality=m2, name="Health")
    archived = Department(municipality=m1, name="Old Unit", status="archived")
    pw = hash_password("retrieval-pass-1")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw)
    member = User(email="member@x.org", role="department_user", municipality=m1,
                  status="active", password_hash=pw, departments=[d1])
    sibling = User(email="sibling@x.org", role="department_user", municipality=m1,
                   status="active", password_hash=pw, departments=[d1b])
    foreign = User(email="foreign@x.org", role="department_user", municipality=m2,
                   status="active", password_hash=pw, departments=[d2])
    db.add_all([m1, m2, d1, d1b, d2, archived, sysadmin, member, sibling, foreign])
    db.commit()
    return {
        "m1": m1, "m2": m2, "d1": d1, "d1b": d1b, "d2": d2, "archived": archived,
        "sys": sysadmin, "member": member, "sibling": sibling, "foreign": foreign,
    }


def add_chunk(db, *, text, visibility, municipality=None, department=None, vector=None):
    from app.models import Chunk
    from app.rag.embeddings import get_embedding_provider

    embedding = vector or get_embedding_provider().embed([text])[0]
    chunk = Chunk(
        source_type="kb",
        source_id=uuid.uuid4(),
        visibility=visibility,
        municipality_id=municipality.id if municipality else None,
        department_id=department.id if department else None,
        content=text,
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()
    return chunk


def retrieve_for(db, user, text):
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    [vec] = get_embedding_provider().embed([text])
    return retrieve(db, query_embedding=vec, user=user, query_text=text)


def test_global_chunk_visible_to_everyone(db, world):
    add_chunk(db, text="Program principles apply to all", visibility="global")
    for who in ("member", "sibling", "foreign", "sys"):
        hits = retrieve_for(db, world[who], "Program principles apply to all")
        assert [h.content for h in hits] == ["Program principles apply to all"], who


def test_municipality_chunk_only_for_its_members(db, world):
    text = "City One internal budget note"
    add_chunk(db, text=text, visibility="municipality", municipality=world["m1"])

    assert [h.content for h in retrieve_for(db, world["member"], text)] == [text]
    assert [h.content for h in retrieve_for(db, world["sibling"], text)] == [text]
    assert retrieve_for(db, world["foreign"], text) == []


def test_department_chunk_only_for_its_members(db, world):
    text = "Welfare intake procedure detail"
    add_chunk(
        db, text=text, visibility="department",
        municipality=world["m1"], department=world["d1"],
    )
    assert [h.content for h in retrieve_for(db, world["member"], text)] == [text]
    # same municipality, different department → nothing
    assert retrieve_for(db, world["sibling"], text) == []
    assert retrieve_for(db, world["foreign"], text) == []


def test_cross_department_leak_returns_nothing(db, world):
    """The acceptance test from the scope appendix: an answer that exists only in
    another department's files must be unreachable."""
    secret = "The confidential Education-only staffing plan"
    add_chunk(
        db, text=secret, visibility="department",
        municipality=world["m1"], department=world["d1b"],
    )
    assert retrieve_for(db, world["member"], secret) == []


def test_archived_department_excluded(db, world):
    text = "Legacy content from an archived unit"
    add_chunk(
        db, text=text, visibility="department",
        municipality=world["m1"], department=world["archived"],
    )
    # even a user who was a member sees nothing once the department is archived
    world["member"].departments.append(world["archived"])
    db.commit()
    assert retrieve_for(db, world["member"], text) == []


def test_inactive_municipality_excluded(db, world):
    text = "City One announcement while active"
    add_chunk(db, text=text, visibility="municipality", municipality=world["m1"])
    assert retrieve_for(db, world["member"], text)

    world["m1"].status = "inactive"
    db.commit()
    assert retrieve_for(db, world["member"], text) == []


def test_low_similarity_dropped(db, world):
    add_chunk(db, text="Completely unrelated subject matter", visibility="global")
    hits = retrieve_for(db, world["member"], "שאלה על נושא אחר לגמרי בעברית")
    assert hits == []


def test_top_k_and_scores(db, world):
    from app.rag.retrieval import MIN_SIMILARITY, TOP_K

    for i in range(TOP_K + 5):
        add_chunk(db, text=f"Shared guidance number {i}", visibility="global")
    hits = retrieve_for(db, world["member"], "Shared guidance number 3")
    assert len(hits) <= TOP_K
    assert hits and hits[0].content == "Shared guidance number 3"
    assert all(h.similarity >= MIN_SIMILARITY for h in hits)
    assert hits == sorted(hits, key=lambda h: -h.similarity)


def test_system_admin_sees_everything(db, world):
    dept_text = "Welfare-only note for the sysadmin test"
    add_chunk(
        db, text=dept_text, visibility="department",
        municipality=world["m1"], department=world["d1"],
    )
    assert [h.content for h in retrieve_for(db, world["sys"], dept_text)] == [dept_text]


# --- hybrid search -----------------------------------------------------------
# The lexical arm is a second way into the same rows, so every permission test
# above must keep passing, and these add the cases dense vectors cannot serve.


def test_exact_token_found_that_dense_retrieval_misses(db, world):
    """Form numbers and regulation references carry little semantic signal;
    lexical matching is what makes them findable."""
    text = "Applications use form 4B under regulation 17.3 of the planning code."
    add_chunk(db, text=text, visibility="global")

    hits = retrieve_for(db, world["member"], "regulation 17.3")
    assert [h.content for h in hits] == [text]
    assert hits[0].from_lexical


def test_lexical_arm_respects_the_permission_filter(db, world):
    """A second retrieval path must not become a way around the boundary."""
    secret = "Education staffing plan uses form 9Z under regulation 42.1"
    add_chunk(
        db, text=secret, visibility="department",
        municipality=world["m1"], department=world["d1b"],
    )
    # an exact-token query that lexical search would certainly match
    assert retrieve_for(db, world["member"], "form 9Z regulation 42.1") == []
    assert retrieve_for(db, world["foreign"], "form 9Z regulation 42.1") == []
    # its own department still finds it
    assert retrieve_for(db, world["sibling"], "form 9Z regulation 42.1")


def test_lexical_arm_excludes_archived_and_inactive_scopes(db, world):
    add_chunk(
        db, text="Archived unit uses form 3C", visibility="department",
        municipality=world["m1"], department=world["archived"],
    )
    world["member"].departments.append(world["archived"])
    db.commit()
    assert retrieve_for(db, world["member"], "form 3C") == []


def test_paraphrased_question_still_finds_the_passage(db, world):
    """Neither arm has to win on its own — this is why both exist. Offline the
    dense arm scores this paraphrase just under the threshold and the lexical
    arm carries it; with real embeddings the dense arm carries it instead."""
    text = "Waste collection operates every Tuesday and Friday in all neighbourhoods"
    add_chunk(db, text=text, visibility="global")
    hits = retrieve_for(db, world["member"], "Which days does waste collection operate?")
    assert hits and hits[0].content == text
    assert hits[0].from_dense or hits[0].from_lexical


def test_dense_arm_works_on_its_own(db, world):
    """A query the lexical arm cannot serve: no shared surface tokens."""
    text = "Waste collection operates every Tuesday and Friday"
    add_chunk(db, text=text, visibility="global")
    hits = retrieve_for(db, world["member"], text)  # exact semantic match
    assert hits and hits[0].from_dense


def test_fusion_ranks_a_chunk_found_by_both_arms_first(db, world):
    both = "Budget planning cycle begins in November for every municipality"
    dense_only = "Budget planning guidance and municipal planning notes"
    add_chunk(db, text=both, visibility="global")
    add_chunk(db, text=dense_only, visibility="global")

    hits = retrieve_for(db, world["member"], "Budget planning cycle begins in November")
    assert hits[0].content == both
    assert hits[0].from_dense and hits[0].from_lexical
    assert hits[0].score >= (hits[1].score if len(hits) > 1 else 0)


def test_unrelated_query_still_returns_nothing(db, world):
    add_chunk(db, text="Waste collection schedule for neighbourhoods", visibility="global")
    assert retrieve_for(db, world["member"], "capital of France population 1970") == []


def test_one_incidental_word_is_not_evidence(db, world):
    """The lexical arm ORs the query terms for recall. Without a floor, an
    unanswerable question matches any chunk sharing a single common word and
    comes back with confident-looking citations instead of "not covered"."""
    add_chunk(
        db,
        text="The municipal budget plan for 2026 covers road maintenance costs",
        visibility="global",
    )
    assert retrieve_for(
        db, world["member"],
        "How many new staffing roles does the education plan allocate?",
    ) == []


def test_short_precise_query_still_matches_on_its_own_terms(db, world):
    """The floor must not price out the queries hybrid search exists to serve."""
    text = "Applications use form 4B under regulation 17.3 of the planning code."
    add_chunk(db, text=text, visibility="global")
    assert [h.content for h in retrieve_for(db, world["member"], "regulation 17.3")] == [text]


def test_lexical_arm_matches_hebrew_tokens(db, world):
    """The tsvector uses the 'english' configuration, which does not stem Hebrew
    but does tokenise it — so exact Hebrew terms are still findable lexically.
    The query embedding here is deliberately unrelated, so a hit can only come
    from the lexical arm."""
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    text = "מכרז 2026/14 לאיסוף פסולת בשכונות הצפון"
    add_chunk(db, text=text, visibility="global")

    [unrelated] = get_embedding_provider().embed(["completely different english text"])
    hits = retrieve(db, query_embedding=unrelated, user=world["member"],
                    query_text="מכרז 2026/14 לאיסוף פסולת")
    assert [h.content for h in hits] == [text]
    assert hits[0].from_lexical and not hits[0].from_dense


def test_hebrew_lexical_hit_still_obeys_permissions(db, world):
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    secret = "מכרז 2026/99 סודי של מחלקת החינוך"
    add_chunk(db, text=secret, visibility="department",
              municipality=world["m1"], department=world["d1b"])

    [unrelated] = get_embedding_provider().embed(["completely different english text"])
    assert retrieve(db, query_embedding=unrelated, user=world["member"],
                    query_text="מכרז 2026/99 סודי") == []


def test_municipality_admin_does_not_retrieve_non_member_department_content(db, world):
    """Deliberate asymmetry from the scope appendix: a municipality admin can
    BROWSE any department area in their municipality, but department content is
    "retrievable by the assistant for members only". Widening the predicate to
    include an admin's whole municipality is the tempting wrong fix."""
    from app.core.security import hash_password
    from app.models import User

    admin = User(
        email="muni.admin@x.org", role="municipality_admin", municipality=world["m1"],
        status="active", password_hash=hash_password("retrieval-pass-1"),
    )
    db.add(admin)
    db.commit()

    text = "Welfare intake procedure for the municipality admin case"
    add_chunk(
        db, text=text, visibility="department",
        municipality=world["m1"], department=world["d1"],
    )
    # same municipality, but not a member of that department
    assert retrieve_for(db, admin, text) == []

    # municipality-wide content is still theirs
    announcement = "City One municipality wide announcement"
    add_chunk(db, text=announcement, visibility="municipality", municipality=world["m1"])
    assert [h.content for h in retrieve_for(db, admin, announcement)] == [announcement]


# --- re-ranking --------------------------------------------------------------


def test_reranking_caps_how_much_one_document_can_dominate(db, world):
    """A long document legitimately holds several relevant passages, but it must
    not fill the whole context window and crowd out the one paragraph elsewhere
    that completes the answer."""
    import uuid as _uuid

    from app.models import Chunk
    from app.rag.embeddings import get_embedding_provider
    from app.rag.reranking import MAX_PER_SOURCE

    hogging_source = _uuid.uuid4()
    for i in range(20):  # more than TOP_K, so the slots are genuinely scarce
        text = f"Waste collection schedule detail paragraph {i} for the northern district"
        db.add(Chunk(
            source_type="kb", source_id=hogging_source, visibility="global",
            content=text, embedding=get_embedding_provider().embed([text])[0],
        ))
    other = "Waste collection schedule contact number for the northern district office"
    add_chunk(db, text=other, visibility="global")
    db.commit()

    hits = retrieve_for(db, world["member"], "Waste collection schedule northern district")
    from_hog = [h for h in hits if h.source_id == hogging_source]
    assert len(from_hog) <= MAX_PER_SOURCE, "one document filled the answer"
    assert any(h.content == other for h in hits), "the second source was crowded out"


def test_reranking_cannot_widen_the_permission_boundary(db, world):
    """Re-ranking runs on rows the SQL already returned, so it can only reorder
    and drop. This is the property that makes it safe to iterate on."""
    secret = "Education staffing plan for the reranking test"
    add_chunk(
        db, text=secret, visibility="department",
        municipality=world["m1"], department=world["d1b"],
    )
    for i in range(20):
        add_chunk(db, text=f"Education staffing guidance note {i}", visibility="global")

    hits = retrieve_for(db, world["member"], "Education staffing plan")
    assert all(h.content != secret for h in hits)
    assert all(h.visibility == "global" for h in hits)


def test_reranking_never_returns_more_than_asked(db, world):
    from app.rag.retrieval import TOP_K

    for i in range(40):
        add_chunk(db, text=f"Municipal procedure number {i} for budget review", visibility="global")
    hits = retrieve_for(db, world["member"], "Municipal procedure budget review")
    assert 0 < len(hits) <= TOP_K


def test_reranking_can_be_turned_off(db, world):
    """The raw fused order stays reachable, so a regression can be isolated."""
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    for i in range(6):
        add_chunk(db, text=f"Recycling centre opening hours variant {i}", visibility="global")
    q = "Recycling centre opening hours"
    [vec] = get_embedding_provider().embed([q])
    plain = retrieve(db, query_embedding=vec, user=world["member"], query_text=q,
                     rerank_results=False)
    assert plain == sorted(plain, key=lambda h: (-h.score, -h.similarity))


# --- graph as a third retrieval arm ------------------------------------------


def _graph_chunk(db, *, text, visibility, municipality=None, department=None):
    """A chunk stored and indexed into the graph, as ingestion does."""
    from app.rag.graph import index_chunk

    chunk = add_chunk(db, text=text, visibility=visibility,
                      municipality=municipality, department=department)
    index_chunk(db, chunk_id=chunk.id, content=text, visibility=visibility,
                municipality_id=chunk.municipality_id,
                department_id=chunk.department_id)
    db.commit()
    return chunk


def test_graph_arm_surfaces_a_passage_the_other_arms_miss(db, world):
    """The case that justifies the graph: the answer lives in a document that
    shares no vocabulary with the question, reachable only through an entity."""
    _graph_chunk(db, text="The Intake Programme requires form 9F", visibility="global")
    bridge = _graph_chunk(
        db, text="Budget Committee approves the Intake Programme", visibility="global",
    )
    hits = retrieve_for(db, world["member"], "Budget Committee")
    assert bridge.id in {h.id for h in hits}
    assert any(h.from_graph for h in hits), "the graph arm contributed nothing"


def test_graph_arm_cannot_widen_the_permission_boundary(db, world):
    """The third arm is a third way in, so it is a third way to leak. It must
    obey the same boundary as the other two."""
    secret = _graph_chunk(
        db, text="Budget Committee approves the Confidential Staffing Plan",
        visibility="department", municipality=world["m1"], department=world["d1b"],
    )
    _graph_chunk(db, text="Budget Committee meets in November", visibility="global")

    hits = retrieve_for(db, world["member"], "Budget Committee")
    assert secret.id not in {h.id for h in hits}
    assert all(h.visibility == "global" for h in hits)

    # its own department still reaches it
    assert secret.id in {h.id for h in retrieve_for(db, world["sibling"], "Budget Committee")}


def test_graph_can_be_turned_off(db, world):
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    _graph_chunk(db, text="Budget Committee approves the Intake Programme", visibility="global")
    q = "Budget Committee"
    [vec] = get_embedding_provider().embed([q])
    hits = retrieve(db, query_embedding=vec, user=world["member"], query_text=q,
                    use_graph=False)
    assert all(not h.from_graph for h in hits)


def test_a_traversal_failure_does_not_take_the_answer_down(db, world, monkeypatch):
    """The graph is an enhancement over search that already works."""
    from app.rag import retrieval as retrieval_mod

    text = "Waste collection operates every Tuesday and Friday"
    add_chunk(db, text=text, visibility="global")

    def boom(*args, **kwargs):
        raise RuntimeError("graph is down")

    monkeypatch.setattr(retrieval_mod, "related_chunk_ids", boom)
    hits = retrieve_for(db, world["member"], text)
    assert hits and hits[0].content == text
