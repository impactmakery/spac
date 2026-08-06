import io

import pytest


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Category, Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    cat = Category(name_he="כלים", name_en="Tools")
    pw = hash_password("board-password-1")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root")
    a1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
              status="active", password_hash=pw, name="Admin One")
    u1 = User(email="u1@x.org", role="department_user", municipality=m1,
              status="active", password_hash=pw, name="Worker One",
              departments=[d1])
    u2 = User(email="u2@x.org", role="department_user", municipality=m2,
              status="active", password_hash=pw, name="Worker Two")
    db.add_all([m1, m2, d1, cat, sysadmin, a1, u1, u2])
    db.commit()
    return {"m1": m1, "m2": m2, "d1": d1, "cat": cat, "u1": u1, "u2": u2, "a1": a1}


def auth(client, email):
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "board-password-1"}
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def publish_link(client, headers, world, *, title="GPT guide", destination="global"):
    return client.post(
        "/api/board-items",
        data={
            "title": title,
            "category_id": str(world["cat"].id),
            "destination": destination,
            "description": "How to write summaries",
            "link_url": "https://example.org/guide",
        },
        headers=headers,
    )


def test_publish_link_and_list(client, db, world):
    headers = auth(client, "u1@x.org")
    r = publish_link(client, headers, world)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["scope"] == "global" and item["link_url"].startswith("https://")
    assert item["author"]["municipality_name"] == "City One"

    page = client.get("/api/board-items?scope=global", headers=headers).json()
    assert [i["title"] for i in page["items"]] == ["GPT guide"]
    assert page["has_more"] is False

    # description was queued for indexing
    from app.models import IngestionJob

    assert db.query(IngestionJob).filter(IngestionJob.source_type == "board").count() == 1


def test_a_post_must_carry_something_and_links_must_be_https(client, world):
    headers = auth(client, "u1@x.org")
    r = client.post(
        "/api/board-items",
        data={
            "title": "No content",
            "category_id": str(world["cat"].id),
            "destination": "global",
        },
        headers=headers,
    )
    assert r.status_code == 422
    r = client.post(
        "/api/board-items",
        data={
            "title": "http link",
            "category_id": str(world["cat"].id),
            "destination": "global",
            "link_url": "http://insecure.example",
        },
        headers=headers,
    )
    assert r.status_code == 422


def test_municipality_board_scoping_404(client, world):
    headers1 = auth(client, "u1@x.org")
    r = publish_link(client, headers1, world, title="City One only",
                     destination="municipality")
    assert r.status_code == 201
    item_id = r.json()["id"]
    assert r.json()["municipality_name" if False else "scope"] == "municipality"

    # member of another municipality: list empty + direct fetch 404
    headers2 = auth(client, "u2@x.org")
    page = client.get("/api/board-items?scope=municipality", headers=headers2).json()
    assert page["items"] == []
    assert (
        client.get(f"/api/board-items/{item_id}", headers=headers2).status_code == 404
    )
    # sysadmin can fetch
    assert (
        client.get(f"/api/board-items/{item_id}", headers=auth(client, "sys@x.org"))
        .status_code
        == 200
    )


def test_like_toggle_and_comments(client, world):
    headers = auth(client, "u1@x.org")
    item_id = publish_link(client, headers, world).json()["id"]

    r = client.post(f"/api/board-items/{item_id}/like", headers=headers)
    assert r.json() == {"liked": True, "like_count": 1}
    r = client.post(f"/api/board-items/{item_id}/like", headers=headers)
    assert r.json() == {"liked": False, "like_count": 0}

    r = client.post(
        f"/api/board-items/{item_id}/comments", json={"body": "great tool"},
        headers=headers,
    )
    assert r.status_code == 201
    comment_id = r.json()["id"]
    detail = client.get(f"/api/board-items/{item_id}", headers=headers).json()
    assert [c["body"] for c in detail["comments"]] == ["great tool"]

    # over-long comment rejected
    r = client.post(
        f"/api/board-items/{item_id}/comments", json={"body": "x" * 1001},
        headers=headers,
    )
    assert r.status_code == 422

    assert (
        client.delete(
            f"/api/board-items/{item_id}/comments/{comment_id}", headers=headers
        ).status_code
        == 200
    )


def test_edit_author_only(client, world):
    headers = auth(client, "u1@x.org")
    item_id = publish_link(client, headers, world).json()["id"]
    patch = {
        "title": "Renamed", "description": "new desc",
        "category_id": str(world["cat"].id),
    }
    other = auth(client, "u2@x.org")
    assert (
        client.patch(f"/api/board-items/{item_id}", json=patch, headers=other)
        .status_code
        == 404
    )
    r = client.patch(f"/api/board-items/{item_id}", json=patch, headers=headers)
    assert r.status_code == 200 and r.json()["title"] == "Renamed"


def test_delete_rules_and_moderation_audit(client, db, world):
    author = auth(client, "u1@x.org")
    item_id = publish_link(client, author, world).json()["id"]

    # unrelated user (other municipality) cannot delete
    assert (
        client.delete(f"/api/board-items/{item_id}", headers=auth(client, "u2@x.org"))
        .status_code
        == 404
    )
    # author's municipality admin CAN delete the global item (moderation) + audit row
    r = client.delete(f"/api/board-items/{item_id}", headers=auth(client, "a1@x.org"))
    assert r.status_code == 200

    from app.models import AuditLog

    assert (
        db.query(AuditLog)
        .filter(AuditLog.action == "board_item.moderate_delete")
        .count()
        == 1
    )


def test_file_item_upload_and_delete_cascades(client, db, world, files_dir):
    import docx

    from app.models import Chunk, IngestionJob
    from app.services.ingestion import run_pending_jobs

    d = docx.Document()
    d.add_paragraph("Annual budget template for municipalities")
    buf = io.BytesIO()
    d.save(buf)

    headers = auth(client, "u1@x.org")
    r = client.post(
        "/api/board-items",
        data={
            "title": "Budget template",
            "category_id": str(world["cat"].id),
            "destination": "global",
        },
        files={
            "file": (
                "budget.docx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]
    run_pending_jobs(db)
    chunks = db.query(Chunk).filter(Chunk.source_type == "board").all()
    assert chunks and any("budget" in c.content.lower() for c in chunks)

    detail = client.get(f"/api/board-items/{item_id}", headers=headers).json()
    assert detail["download_url"].startswith("/api/files/board/")

    assert client.delete(f"/api/board-items/{item_id}", headers=headers).status_code == 200
    assert db.query(Chunk).filter(Chunk.source_type == "board").count() == 0
    assert db.query(IngestionJob).filter(IngestionJob.source_type == "board").count() == 0


def test_search_and_category_filter(client, db, world):
    from app.models import Category

    headers = auth(client, "u1@x.org")
    other_cat = Category(name_he="טפסים", name_en="Forms")
    db.add(other_cat)
    db.commit()
    publish_link(client, headers, world, title="Hebrew guide שיטות עבודה")
    publish_link(client, headers, world, title="Budget forms")

    page = client.get("/api/board-items?search=שיטות", headers=headers).json()
    assert [i["title"] for i in page["items"]] == ["Hebrew guide שיטות עבודה"]
    page = client.get(
        f"/api/board-items?category_id={other_cat.id}", headers=headers
    ).json()
    assert page["items"] == []



# --- shared prompts and agents -----------------------------------------------


def publish_prompt(client, headers, world, **extra):
    data = {
        "title": "פרומפט לניסוח מכתב לתושב",
        "category_id": str(world["cat"].id),
        "destination": "global",
        "prompt_text": "אתה עוזר בעירייה. נסח תשובה מנומסת בעברית לפניית תושב.",
    }
    data.update(extra)
    return client.post("/api/board-items", data=data, headers=headers)


def test_publish_a_prompt_with_no_file_and_no_link(client, world):
    """A shared prompt is content in its own right. The previous rule demanded a
    file or a link, which would have rejected the most useful kind of post."""
    res = publish_prompt(client, auth(client, "u1@x.org"), world)
    assert res.status_code == 201, res.text
    body = res.json()
    assert "אתה עוזר בעירייה" in body["prompt_text"]
    assert body["link_url"] is None and body["filename"] is None


def test_a_prompt_may_travel_with_a_link_to_where_the_agent_lives(client, world):
    res = publish_prompt(
        client, auth(client, "u1@x.org"), world,
        title="Resident enquiry agent",
        link_url="https://example.org/agents/resident-enquiry",
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["prompt_text"] and body["link_url"]


def test_a_shared_prompt_is_findable_by_the_assistant(client, db, world):
    """Storing the prompt as text is what makes it searchable — otherwise a
    colleague can only find it by scrolling the board."""
    import uuid

    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    res = publish_prompt(
        client, auth(client, "u1@x.org"), world,
        title="Tender summary prompt",
        prompt_text="Summarise a tender document under regulation 17.3 in Hebrew",
    )
    assert res.status_code == 201
    item_id = uuid.UUID(res.json()["id"])

    run_pending_jobs(db)
    chunks = db.query(Chunk).filter(Chunk.source_id == item_id).all()
    assert chunks, "the prompt was never indexed"
    assert any("regulation 17.3" in c.content for c in chunks)


def test_any_file_type_can_be_attached_to_a_post(client, db, world, files_dir):
    """Unrestricted uploads are a product decision; an unreadable type must not
    fail the post."""
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "u1@x.org")
    res = client.post(
        "/api/board-items",
        data={
            "title": "Team screenshot",
            "category_id": str(world["cat"].id),
            "destination": "global",
        },
        files={"file": ("diagram.zip", b"PK\x03\x04nonsense", "application/zip")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["filename"] == "diagram.zip"

    run_pending_jobs(db)  # must not raise on a type it cannot read
