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
    return retrieve(db, query_embedding=vec, user=user)


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
