"""Server errors outlive the container that produced them.

Railway keeps logs for seven days and only whoever deploys can read them, so a
municipality reporting on Monday that something broke a fortnight ago was
simply unanswerable. These rows are that answer.

The page is a system admin's, and the reason it is not merged into one stream
is that its three sources have different owners: a server error wants a
developer, a document that would not index usually wants the file re-saved,
and a failed cron usually means the digest did not go out.
"""

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Municipality, User

    pw = hash_password("errors-pw-11")
    muni = Municipality(name="City")
    db.add(muni)
    db.flush()
    db.add_all(
        [
            User(email="root@x.org", role="system_admin", status="active",
                 password_hash=pw, name="Root"),
            User(email="admin@x.org", role="municipality_admin", municipality=muni,
                 status="active", password_hash=pw, name="Admin"),
            User(email="worker@x.org", role="department_user", municipality=muni,
                 status="active", password_hash=pw, name="Worker"),
        ]
    )
    db.commit()
    return {"muni": muni}


def auth(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "errors-pw-11"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_an_error_is_recorded_with_what_is_needed_to_find_it(db):
    from app.models import ErrorLog
    from app.services.error_log import record_error

    try:
        raise ValueError("the thing went wrong")
    except ValueError as exc:
        record_error(db, method="POST", path="/api/board-items", status_code=500, exc=exc)

    row = db.query(ErrorLog).one()
    assert row.method == "POST"
    assert row.path == "/api/board-items"
    assert row.error_type == "ValueError"
    assert "the thing went wrong" in row.message
    assert "ValueError" in (row.traceback or "")


def test_recording_a_failure_never_raises(db, monkeypatch):
    """This runs while a request is already failing. If it threw, the caller
    would lose its 500 and get nothing at all."""
    from app.services import error_log

    def explode(*a, **k):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(db, "add", explode)
    try:
        raise ValueError("original")
    except ValueError as exc:
        error_log.record_error(db, method="GET", path="/x", status_code=500, exc=exc)
    # reaching here is the assertion


def test_a_giant_error_is_truncated_rather_than_stored_whole(db):
    from app.models import ErrorLog
    from app.services.error_log import MAX_MESSAGE, MAX_TRACEBACK, record_error

    try:
        raise ValueError("x" * (MAX_MESSAGE * 3))
    except ValueError as exc:
        record_error(db, method="GET", path="/x", status_code=500, exc=exc)

    row = db.query(ErrorLog).one()
    assert len(row.message) <= MAX_MESSAGE
    assert len(row.traceback or "") <= MAX_TRACEBACK


def test_the_query_string_is_not_stored(db):
    """A system admin reads every municipality's errors at once, and query
    strings carry search terms and ids."""
    from app.models import ErrorLog
    from app.services.error_log import record_error

    try:
        raise ValueError("boom")
    except ValueError as exc:
        record_error(db, method="GET", path="/api/board-items", status_code=500, exc=exc)

    assert "?" not in db.query(ErrorLog).one().path


def test_old_errors_are_pruned(db):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.models import ErrorLog
    from app.services.error_log import RETENTION_DAYS, prune_errors, record_error

    try:
        raise ValueError("old one")
    except ValueError as exc:
        record_error(db, method="GET", path="/x", status_code=500, exc=exc)
    db.execute(
        text("UPDATE error_log SET occurred_at = :t"),
        {"t": datetime.now(UTC) - timedelta(days=RETENTION_DAYS + 1)},
    )
    db.commit()

    assert prune_errors(db) == 1
    assert db.query(ErrorLog).count() == 0


def test_a_real_unhandled_error_reaches_the_table(db, engine, monkeypatch):
    """The handler is the only thing that fills this table. If it is not wired
    up the page is permanently empty and says everything is fine."""
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session, sessionmaker

    from app.core import db as db_module
    from app.core.db import get_db
    from app.main import create_app
    from app.models import ErrorLog

    # The handler opens its own session, on purpose — the request's own is
    # inside a failed transaction by then. Point that factory at this test's
    # database, or the row lands in whatever DATABASE_URL happens to name.
    monkeypatch.setattr(db_module, "_session_factory", sessionmaker(bind=engine))

    app = create_app()

    @app.get("/api/__boom")
    def boom() -> None:
        raise RuntimeError("something nobody caught")

    def override():
        s = Session(bind=engine)
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/__boom")

    assert r.status_code == 500
    # The caller still learns nothing: the detail belongs on the errors page.
    assert r.json() == {"detail": "server_error"}

    row = db.query(ErrorLog).filter_by(path="/api/__boom").one()
    assert row.error_type == "RuntimeError"
    assert "something nobody caught" in row.message


def test_the_daily_purge_sweeps_old_errors(client, db):
    """prune_errors only helps if something calls it."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from app.core.config import get_settings
    from app.models import ErrorLog
    from app.services.error_log import RETENTION_DAYS, record_error

    try:
        raise ValueError("ancient")
    except ValueError as exc:
        record_error(db, method="GET", path="/x", status_code=500, exc=exc)
    db.execute(
        text("UPDATE error_log SET occurred_at = :t"),
        {"t": datetime.now(UTC) - timedelta(days=RETENTION_DAYS + 1)},
    )
    db.commit()

    r = client.post(
        "/api/cron/archive-purge",
        headers={"Authorization": f"Bearer {get_settings().cron_secret}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["errors_purged"] == 1
    assert db.query(ErrorLog).count() == 0


# --- the page ---------------------------------------------------------------


@pytest.mark.parametrize("email", ["admin@x.org", "worker@x.org"])
def test_only_a_system_admin_may_read_the_errors(client, world, email):
    """Tracebacks name paths and ids across every municipality."""
    assert client.get("/api/system/errors", headers=auth(client, email)).status_code == 404


def test_a_system_admin_sees_the_three_kinds_separately(client, db, world):
    from app.models import CronRun, KbDocument, User
    from app.services.error_log import record_error

    root = db.query(User).filter_by(email="root@x.org").one()
    try:
        raise ValueError("a defect")
    except ValueError as exc:
        record_error(db, method="GET", path="/api/chat", status_code=500, exc=exc,
                     user_id=root.id)

    db.add(KbDocument(title="Broken scan", filename="scan.pdf", storage_key="k",
                      size_bytes=1, content_type="application/pdf", uploader_id=root.id,
                      status="not_indexable", error="could not extract", scope="global"))
    db.add(CronRun(job="digest", period_key="2026-W33", error="smtp refused"))
    db.commit()

    body = client.get("/api/system/errors", headers=auth(client, "root@x.org")).json()
    assert [e["error_type"] for e in body["server_errors"]] == ["ValueError"]
    assert body["server_errors"][0]["user_email"] == "root@x.org"
    assert [d["filename"] for d in body["failed_documents"]] == ["scan.pdf"]
    assert [j["job"] for j in body["failed_jobs"]] == ["digest"]


def test_a_failed_document_can_be_put_back_in_the_queue(client, db, world):
    """A page that can only be read is a page nobody opens twice."""
    from app.models import IngestionJob, KbDocument, User

    root = db.query(User).filter_by(email="root@x.org").one()
    doc = KbDocument(title="Retry me", filename="a.docx", storage_key="k", size_bytes=1,
                     content_type="application/octet-stream", uploader_id=root.id,
                     status="not_indexable", error="transient", scope="global")
    db.add(doc)
    db.commit()

    r = client.post(f"/api/system/errors/documents/{doc.id}/retry",
                    headers=auth(client, "root@x.org"))
    assert r.status_code == 200
    assert r.json()["requeued"] == 1

    db.expire_all()
    assert db.get(KbDocument, doc.id).status == "pending"
    assert db.get(KbDocument, doc.id).error is None
    assert db.query(IngestionJob).filter_by(source_id=doc.id).count() == 1


def test_retrying_keeps_a_document_in_its_own_library(client, db, world):
    """The scope is re-sent with the job, and taking it from anywhere but the
    document would republish one municipality's library to all of them."""
    from app.models import IngestionJob, KbDocument, User

    root = db.query(User).filter_by(email="root@x.org").one()
    doc = KbDocument(title="Ours only", filename="a.docx", storage_key="k", size_bytes=1,
                     content_type="application/octet-stream", uploader_id=root.id,
                     status="not_indexable", scope="municipality",
                     municipality_id=world["muni"].id)
    db.add(doc)
    db.commit()

    client.post(f"/api/system/errors/documents/{doc.id}/retry",
                headers=auth(client, "root@x.org"))

    job = db.query(IngestionJob).filter_by(source_id=doc.id).one()
    assert job.payload["visibility"] == "municipality"
    assert job.payload["municipality_id"] == str(world["muni"].id)


def test_a_department_file_can_be_retried_too(client, db, world):
    """It is listed beside the library documents, so the button beside it has
    to work. A file that got only a cheerful toast and no new job would be
    worse than no button at all."""
    from app.models import Department, DepartmentFile, IngestionJob, User

    root = db.query(User).filter_by(email="root@x.org").one()
    dept = Department(name="Welfare", municipality_id=world["muni"].id)
    db.add(dept)
    db.flush()
    f = DepartmentFile(department_id=dept.id, uploader_id=root.id, filename="notes.docx",
                       storage_key="k", size_bytes=1,
                       content_type="application/octet-stream",
                       status="not_indexable", error="transient")
    db.add(f)
    db.commit()

    body = client.get("/api/system/errors", headers=auth(client, "root@x.org")).json()
    listed = [d for d in body["failed_documents"] if d["filename"] == "notes.docx"]
    assert listed and listed[0]["library"] == "City · Welfare"

    r = client.post(f"/api/system/errors/documents/{f.id}/retry",
                    headers=auth(client, "root@x.org"))
    assert r.status_code == 200

    db.expire_all()
    assert db.get(DepartmentFile, f.id).status == "pending"
    job = db.query(IngestionJob).filter_by(source_id=f.id).one()
    assert job.source_type == "department"
    # The scope travels in the payload, and getting it wrong here would put a
    # department's file where the whole platform can read it.
    assert job.payload["visibility"] == "department"
    assert job.payload["department_id"] == str(dept.id)


def test_retrying_something_that_is_gone_says_so(client, db, world):
    """Silence would read as success on a page whose whole job is telling the
    truth about what failed."""
    import uuid

    r = client.post(f"/api/system/errors/documents/{uuid.uuid4()}/retry",
                    headers=auth(client, "root@x.org"))
    assert r.status_code == 404


@pytest.mark.parametrize("email", ["admin@x.org", "worker@x.org"])
def test_nobody_else_may_retry(client, db, world, email):
    from app.models import KbDocument, User

    root = db.query(User).filter_by(email="root@x.org").one()
    doc = KbDocument(title="Retry me", filename="a.docx", storage_key="k", size_bytes=1,
                     content_type="application/octet-stream", uploader_id=root.id,
                     status="not_indexable", scope="global")
    db.add(doc)
    db.commit()

    r = client.post(f"/api/system/errors/documents/{doc.id}/retry",
                    headers=auth(client, email))
    assert r.status_code == 404
