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
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    d1b = Department(municipality=m1, name="Education")
    d2 = Department(municipality=m2, name="Health")
    pw = hash_password("dept-password-11")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root")
    a1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
              status="active", password_hash=pw, name="Admin One")
    member = User(email="member@x.org", role="department_user", municipality=m1,
                  status="active", password_hash=pw, name="Member",
                  departments=[d1])
    outsider = User(email="outsider@x.org", role="department_user", municipality=m1,
                    status="active", password_hash=pw, name="Outsider",
                    departments=[d1b])
    foreign = User(email="foreign@x.org", role="department_user", municipality=m2,
                   status="active", password_hash=pw, name="Foreign",
                   departments=[d2])
    db.add_all([m1, m2, d1, d1b, d2, sysadmin, a1, member, outsider, foreign])
    db.commit()
    return {"d1": d1, "d2": d2, "m1": m1}


def auth(client, email):
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "dept-password-11"}
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _docx(text="Departmental procedure for intake meetings") -> bytes:
    import docx

    d = docx.Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_member_uploads_file_indexed_with_department_visibility(
    client, db, world, files_dir
):
    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "member@x.org")
    dept_id = world["d1"].id
    r = client.post(
        f"/api/departments/{dept_id}/files",
        files={"file": ("procedure.docx", _docx(), DOCX_MIME)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    run_pending_jobs(db)
    chunk = db.query(Chunk).filter(Chunk.source_type == "department").one()
    assert chunk.visibility == "department"
    assert chunk.department_id == dept_id
    assert chunk.municipality_id == world["m1"].id

    files = client.get(f"/api/departments/{dept_id}/files", headers=headers).json()
    assert files[0]["status"] == "indexed"
    assert files[0]["download_url"].startswith("/api/files/department/")


def test_posts_with_comments_and_indexing(client, db, world, files_dir):
    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "member@x.org")
    dept_id = world["d1"].id
    r = client.post(
        f"/api/departments/{dept_id}/posts",
        json={"body": "Team meeting moved to Thursday at nine."},
        headers=headers,
    )
    assert r.status_code == 201
    post_id = r.json()["id"]

    run_pending_jobs(db)
    chunk = db.query(Chunk).filter(Chunk.source_type == "department").one()
    assert "Thursday" in chunk.content and chunk.visibility == "department"

    r = client.post(
        f"/api/departments/{dept_id}/posts/{post_id}/comments",
        json={"body": "noted"},
        headers=headers,
    )
    assert r.status_code == 201
    posts = client.get(f"/api/departments/{dept_id}/posts", headers=headers).json()
    assert [c["body"] for c in posts[0]["comments"]] == ["noted"]

    assert (
        client.delete(f"/api/departments/{dept_id}/posts/{post_id}", headers=headers)
        .status_code
        == 200
    )
    assert db.query(Chunk).filter(Chunk.source_type == "department").count() == 0


def test_post_length_limit(client, world):
    headers = auth(client, "member@x.org")
    r = client.post(
        f"/api/departments/{world['d1'].id}/posts",
        json={"body": "x" * 2001},
        headers=headers,
    )
    assert r.status_code == 422


def test_non_member_and_foreign_municipality_404(client, world, files_dir):
    dept_id = world["d1"].id
    for email in ("outsider@x.org", "foreign@x.org"):
        headers = auth(client, email)
        assert (
            client.get(f"/api/departments/{dept_id}/files", headers=headers).status_code
            == 404
        )
        assert (
            client.get(f"/api/departments/{dept_id}/posts", headers=headers).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/departments/{dept_id}/posts", json={"body": "hi"}, headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/departments/{dept_id}/files",
                files={"file": ("x.docx", _docx(), DOCX_MIME)},
                headers=headers,
            ).status_code
            == 404
        )


def test_municipality_admin_and_sysadmin_have_access(client, world, files_dir):
    dept_id = world["d1"].id
    for email in ("a1@x.org", "sys@x.org"):
        headers = auth(client, email)
        assert (
            client.get(f"/api/departments/{dept_id}/files", headers=headers).status_code
            == 200
        )
    # municipality admin of City One cannot reach City Two's department
    headers = auth(client, "a1@x.org")
    assert (
        client.get(f"/api/departments/{world['d2'].id}/files", headers=headers).status_code
        == 404
    )


def test_file_delete_cascades_chunks(client, db, world, files_dir):
    from app.models import Chunk, IngestionJob
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "member@x.org")
    dept_id = world["d1"].id
    file_id = client.post(
        f"/api/departments/{dept_id}/files",
        files={"file": ("p.docx", _docx(), DOCX_MIME)},
        headers=headers,
    ).json()["id"]
    run_pending_jobs(db)
    assert db.query(Chunk).count() == 1

    assert (
        client.delete(f"/api/departments/{dept_id}/files/{file_id}", headers=headers)
        .status_code
        == 200
    )
    assert db.query(Chunk).count() == 0
    assert db.query(IngestionJob).count() == 0
