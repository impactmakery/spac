import uuid

import pytest


@pytest.fixture(autouse=True)
def _reset_chat_limit():
    from app.routers.chat import chat_limiter

    chat_limiter._hits.clear()
    yield


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Department, KbDocument, Municipality, User

    m1 = Municipality(name="City One")
    d1 = Department(municipality=m1, name="Welfare")
    d2 = Department(municipality=m1, name="Education")
    pw = hash_password("chat-password-11")
    member = User(email="member@x.org", role="department_user", municipality=m1,
                  status="active", password_hash=pw, name="Member", departments=[d1])
    other = User(email="other@x.org", role="department_user", municipality=m1,
                 status="active", password_hash=pw, name="Other", departments=[d2])
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root")
    doc = KbDocument(
        title="Waste Collection Guidelines",
        filename="waste.docx",
        storage_key="kb/x/waste.docx",
        size_bytes=100,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        status="indexed",
    )
    db.add_all([m1, d1, d2, member, other, sysadmin, doc])
    db.commit()
    return {"m1": m1, "d1": d1, "d2": d2, "member": member, "other": other,
            "sys": sysadmin, "doc": doc}


def auth(client, email):
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "chat-password-11"}
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_chunk(db, text, *, source_type="kb", source_id=None, visibility="global",
              municipality=None, department=None):
    from app.models import Chunk
    from app.rag.embeddings import get_embedding_provider

    [vec] = get_embedding_provider().embed([text])
    chunk = Chunk(
        source_type=source_type,
        source_id=source_id or uuid.uuid4(),
        visibility=visibility,
        municipality_id=municipality.id if municipality else None,
        department_id=department.id if department else None,
        content=text,
        embedding=vec,
    )
    db.add(chunk)
    db.commit()
    return chunk


def parse_sse(text_body: str) -> dict[str, list]:
    import json

    events: dict[str, list] = {}
    for block in text_body.strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        name = lines[0].removeprefix("event: ")
        payload = json.loads(lines[1].removeprefix("data: "))
        events.setdefault(name, []).append(payload)
    return events


def ask(client, headers, convo_id, question):
    r = client.post(
        f"/api/chat/{convo_id}/messages", json={"content": question}, headers=headers
    )
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def test_answer_streams_with_citations(client, db, world):
    text = "Waste is collected every Tuesday and Friday in all neighbourhoods."
    add_chunk(db, text, source_id=world["doc"].id)

    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    events = ask(client, headers, convo_id, "When is waste collected every Tuesday?")

    answer = "".join(events["token"])
    assert "Tuesday" in answer and "[1]" in answer
    citations = events["citations"][0]
    assert len(citations) == 1
    assert citations[0]["title"] == "Waste Collection Guidelines"
    assert citations[0]["href"] == f"/knowledge/{world['doc'].id}"
    assert events["done"]

    # both messages persisted with citations on the answer
    messages = client.get(
        f"/api/conversations/{convo_id}/messages", headers=headers
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["citations"][0]["title"] == "Waste Collection Guidelines"

    # retrieval audit row written
    from app.models import MessageDebug

    debug = db.query(MessageDebug).one()
    assert debug.chunk_ids and debug.scores and debug.prompt
    assert "visibility = 'global'" in debug.retrieval_sql


def test_hebrew_question_answered_in_hebrew(client, db, world):
    """Offline embeddings are lexical (see FakeEmbeddings), so the test question
    shares vocabulary with the source. Production uses multilingual embeddings
    that match across Hebrew morphology."""
    add_chunk(db, "פינוי האשפה מתבצע בימי שלישי ושישי בכל השכונות.", source_id=world["doc"].id)
    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    events = ask(client, headers, convo_id, "מתי מתבצע פינוי האשפה?")
    answer = "".join(events["token"])
    assert "על סמך החומר" in answer and "שלישי" in answer


def test_unanswerable_question_logs_and_replies_not_covered(client, db, world):
    from app.models import Message, UnansweredQuestion

    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    events = ask(client, headers, convo_id, "What is the capital of France?")

    answer = "".join(events["token"])
    assert "does not cover" in answer
    assert events["citations"][0] == []

    row = db.query(UnansweredQuestion).one()
    assert row.question == "What is the capital of France?"
    assert row.user_id == world["member"].id

    assistant = db.query(Message).filter(Message.role == "assistant").one()
    assert assistant.citations is None


def test_cross_department_content_never_answers(client, db, world):
    """The leak acceptance test, end to end through the chat endpoint."""
    from app.models import UnansweredQuestion

    secret = "The Education staffing plan allocates four new roles in September."
    add_chunk(
        db, secret, source_type="department", visibility="department",
        municipality=world["m1"], department=world["d2"],
    )
    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    events = ask(client, headers, convo_id, "How many new roles does the staffing plan add?")

    answer = "".join(events["token"])
    assert "staffing plan allocates" not in answer
    assert "does not cover" in answer
    assert db.query(UnansweredQuestion).count() == 1


def test_conversation_is_private_even_from_system_admin(client, world):
    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]

    for email in ("other@x.org", "sys@x.org"):
        foreign = auth(client, email)
        assert (
            client.get(
                f"/api/conversations/{convo_id}/messages", headers=foreign
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/chat/{convo_id}/messages",
                json={"content": "peek"},
                headers=foreign,
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/conversations/{convo_id}", headers=foreign).status_code
            == 404
        )
        assert client.get("/api/conversations", headers=foreign).json() == []


def test_conversation_auto_title_rename_and_delete(client, world):
    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    ask(client, headers, convo_id, "What are the recycling rules?")

    rows = client.get("/api/conversations", headers=headers).json()
    assert rows[0]["title"] == "What are the recycling rules?"

    r = client.patch(
        f"/api/conversations/{convo_id}", json={"title": "Recycling"}, headers=headers
    )
    assert r.status_code == 200 and r.json()["title"] == "Recycling"

    assert client.delete(f"/api/conversations/{convo_id}", headers=headers).status_code == 200
    assert client.get("/api/conversations", headers=headers).json() == []


def test_rate_limit_60_per_hour(client, db, world):
    from app.routers.chat import chat_limiter

    headers = auth(client, "member@x.org")
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    for _ in range(60):
        chat_limiter.hit(str(world["member"].id))
    r = client.post(
        f"/api/chat/{convo_id}/messages", json={"content": "one too many"},
        headers=headers,
    )
    assert r.status_code == 429


def test_sample_questions_from_kb_titles(client, world):
    headers = auth(client, "member@x.org")
    qs = client.get("/api/chat/sample-questions", headers=headers).json()
    assert qs and "Waste Collection Guidelines" in qs[0]
