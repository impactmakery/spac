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
    from app.models import Municipality, User

    m1 = Municipality(name="City One")
    pw = hash_password("kb-password-111")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root")
    a1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
              status="active", password_hash=pw, name="Admin")
    u1 = User(email="u1@x.org", role="department_user", municipality=m1,
              status="active", password_hash=pw, name="Worker")
    db.add_all([m1, sysadmin, a1, u1])
    db.commit()
    return {"m1": m1, "sys": sysadmin, "a1": a1, "u1": u1}


def auth(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "kb-password-111"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _docx(text="Municipal waste collection guidelines 2026") -> bytes:
    import docx

    d = docx.Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(client, headers, filename="guide.docx", content=None, title=None):
    data = {"title": title} if title else {}
    return client.post(
        "/api/kb-documents",
        files={"file": (filename, content or _docx(), DOCX_MIME)},
        data=data,
        headers=headers,
    )


def test_upload_list_download_flow(client, db, world, files_dir):
    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "a1@x.org")
    r = _upload(client, headers, title="Waste Guide")
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert r.json()["status"] == "pending"
    assert r.json()["municipality_name"] == "City One"

    run_pending_jobs(db)

    # department user can list + open detail with download url
    user_headers = auth(client, "u1@x.org")
    rows = client.get("/api/kb-documents", headers=user_headers).json()
    assert [d["title"] for d in rows] == ["Waste Guide"]
    assert rows[0]["status"] == "indexed"

    detail = client.get(f"/api/kb-documents/{doc_id}", headers=user_headers).json()
    assert detail["download_url"].startswith("/api/files/kb/")
    # signed URL serves without auth
    assert client.get(detail["download_url"]).status_code == 200

    assert db.query(Chunk).count() == 1

    # search
    assert client.get("/api/kb-documents?search=waste", headers=user_headers).json()
    assert client.get("/api/kb-documents?search=zzz", headers=user_headers).json() == []


def test_department_user_cannot_upload(client, world, files_dir):
    headers = auth(client, "u1@x.org")
    assert _upload(client, headers).status_code == 404


def test_upload_rejects_bad_files(client, world, files_dir):
    headers = auth(client, "a1@x.org")
    r = client.post(
        "/api/kb-documents",
        files={"file": ("run.exe", b"MZ...", "application/octet-stream")},
        headers=headers,
    )
    assert r.status_code == 415


def test_replace_keeps_id_and_reindexes(client, db, world, files_dir):
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "a1@x.org")
    doc_id = _upload(client, headers).json()["id"]
    run_pending_jobs(db)

    r = client.post(
        f"/api/kb-documents/{doc_id}/replace",
        files={"file": ("v2.docx", _docx("Second edition of the rules"), DOCX_MIME)},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == doc_id and r.json()["status"] == "pending"
    run_pending_jobs(db)

    from app.models import Chunk

    chunks = db.query(Chunk).all()
    assert len(chunks) == 1 and "Second edition" in chunks[0].content


def test_replace_delete_scoped_to_uploader_or_sysadmin(client, db, world, files_dir):
    from app.core.security import hash_password
    from app.models import Municipality, User

    m2 = Municipality(name="City Two")
    a2 = User(email="a2@x.org", role="municipality_admin", municipality=m2,
              status="active", password_hash=hash_password("kb-password-111"))
    db.add_all([m2, a2])
    db.commit()

    doc_id = _upload(client, auth(client, "a1@x.org")).json()["id"]
    other = auth(client, "a2@x.org")
    assert (
        client.post(
            f"/api/kb-documents/{doc_id}/replace",
            files={"file": ("x.docx", _docx(), DOCX_MIME)},
            headers=other,
        ).status_code
        == 404
    )
    assert client.delete(f"/api/kb-documents/{doc_id}", headers=other).status_code == 404
    # sysadmin can delete anything
    assert (
        client.delete(f"/api/kb-documents/{doc_id}", headers=auth(client, "sys@x.org"))
        .status_code
        == 200
    )


def test_delete_cascades_chunks_same_transaction(client, db, world, files_dir):
    from app.models import Chunk, IngestionJob
    from app.services.ingestion import run_pending_jobs

    headers = auth(client, "a1@x.org")
    doc_id = _upload(client, headers).json()["id"]
    run_pending_jobs(db)
    assert db.query(Chunk).count() == 1

    assert client.delete(f"/api/kb-documents/{doc_id}", headers=headers).status_code == 200
    db.expire_all()
    assert db.query(Chunk).count() == 0
    assert db.query(IngestionJob).count() == 0
    assert client.get(f"/api/kb-documents/{doc_id}", headers=headers).status_code == 404


# --- text preview -------------------------------------------------------------
# A browser cannot render Word, PowerPoint or Excel in a frame, and the
# knowledge base is mostly Word. The text is already extracted for the
# assistant, so previewing it costs nothing new.


def test_word_document_text_can_be_previewed(client, world, files_dir):
    sys_headers = auth(client, "sys@x.org")
    doc_id = _upload(
        client, sys_headers, filename="procedure.docx",
        content=_docx("Waste collection operates on Mondays and Thursdays"),
    ).json()["id"]

    res = client.get(f"/api/kb-documents/{doc_id}/text", headers=sys_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is True
    assert "Mondays and Thursdays" in body["text"]
    assert body["truncated"] is False


def test_a_long_document_is_truncated_rather_than_sent_whole(
    client, world, files_dir, monkeypatch
):
    sys_headers = auth(client, "sys@x.org")
    from app.routers import kb_documents

    monkeypatch.setattr(kb_documents, "MAX_PREVIEW_CHARS", 50)
    doc_id = _upload(
        client, sys_headers, filename="long.docx",
        content=_docx("word " * 500),
    ).json()["id"]

    body = client.get(f"/api/kb-documents/{doc_id}/text", headers=sys_headers).json()
    assert body["truncated"] is True
    assert len(body["text"]) == 50


def test_a_format_with_no_extractor_reports_no_preview(
    client, world, files_dir, db
):
    """Rather than erroring: the page falls back to 'download the file'."""
    sys_headers = auth(client, "sys@x.org")
    from app.models import KbDocument

    doc = KbDocument(
        title="Archive", filename="bundle.zip", storage_key="kb/x/bundle.zip",
        size_bytes=10, content_type="application/octet-stream",
    )
    db.add(doc)
    db.commit()

    body = client.get(f"/api/kb-documents/{doc.id}/text", headers=sys_headers).json()
    assert body["available"] is False and body["text"] == ""


def test_a_missing_file_does_not_break_the_page(client, world, files_dir, db):
    sys_headers = auth(client, "sys@x.org")
    from app.models import KbDocument

    doc = KbDocument(
        title="Gone", filename="gone.docx", storage_key="kb/x/never-written.docx",
        size_bytes=10, content_type="application/vnd.openxmlformats-officedocument"
                                    ".wordprocessingml.document",
    )
    db.add(doc)
    db.commit()

    res = client.get(f"/api/kb-documents/{doc.id}/text", headers=sys_headers)
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_the_preview_needs_a_signed_in_user(client, world, files_dir):
    sys_headers = auth(client, "sys@x.org")
    doc_id = _upload(client, sys_headers, filename="p.docx",
                     content=_docx("anything")).json()["id"]
    assert client.get(f"/api/kb-documents/{doc_id}/text").status_code == 401
