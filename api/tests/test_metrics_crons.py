from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture()
def outbox(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "outbox_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def cron_headers():
    from app.core.config import get_settings

    return {"Authorization": f"Bearer {get_settings().cron_secret}"}


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Category, Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    cat = Category(name_he="כלים", name_en="Tools")
    pw = hash_password("metrics-pass-11")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root")
    admin1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
                  status="active", password_hash=pw, name="Admin One")
    worker = User(email="w1@x.org", role="department_user", municipality=m1,
                  status="active", password_hash=pw, name="Worker", departments=[d1])
    other = User(email="w2@x.org", role="department_user", municipality=m2,
                 status="active", password_hash=pw, name="Other")
    db.add_all([m1, m2, d1, cat, sysadmin, admin1, worker, other])
    db.commit()
    return {"m1": m1, "m2": m2, "d1": d1, "cat": cat, "worker": worker}


def auth(client, email):
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "metrics-pass-11"}
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cron_requires_secret(client):
    assert client.post("/api/cron/metrics-rollup").status_code == 401
    assert (
        client.post(
            "/api/cron/metrics-rollup", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )


def test_rollup_counts_activity_and_is_idempotent(client, db, world, cron_headers):
    from app.models import DailyMetric
    from app.services.metrics import TZ

    # a login, a board item, and a chat message today
    headers = auth(client, "w1@x.org")
    client.post(
        "/api/board-items",
        data={
            "title": "Guide",
            "category_id": str(world["cat"].id),
            "destination": "global",
            "link_url": "https://example.org/guide",
        },
        headers=headers,
    )
    convo = client.post("/api/conversations", headers=headers).json()["id"]
    client.post(
        f"/api/chat/{convo}/messages", json={"content": "hello"}, headers=headers
    )

    today = datetime.now(TZ).date().isoformat()
    r = client.post(f"/api/cron/metrics-rollup?day={today}", headers=cron_headers)
    assert r.status_code == 200, r.text
    assert r.json()["rows"] >= 3  # platform + 2 municipalities (+ departments)

    platform = db.scalar(
        __import__("sqlalchemy").select(DailyMetric).where(
            DailyMetric.municipality_id.is_(None), DailyMetric.department_id.is_(None)
        )
    )
    assert platform.active_users == 1
    assert platform.board_items == 1
    assert platform.chat_sessions == 1 and platform.chat_messages == 1

    # second call in the same period is a no-op, and rows are not duplicated
    again = client.post(f"/api/cron/metrics-rollup?day={today}", headers=cron_headers)
    assert again.json()["skipped"] == "already_ran"
    total = db.query(DailyMetric).filter(
        DailyMetric.municipality_id.is_(None), DailyMetric.department_id.is_(None)
    ).count()
    assert total == 1


def test_municipality_stats_scoped_and_from_rollups(client, db, world, cron_headers):
    from app.services.metrics import TZ

    auth(client, "w1@x.org")  # a login for City One
    today = datetime.now(TZ).date().isoformat()
    client.post(f"/api/cron/metrics-rollup?day={today}", headers=cron_headers)

    admin = auth(client, "a1@x.org")
    stats = client.get("/api/stats/municipality?range_days=7", headers=admin).json()
    assert stats["range_days"] == 7
    assert stats["kpis"]["active_users"] >= 1
    assert [b["name"] for b in stats["breakdown"]] == ["Welfare"]
    assert len(stats["series"]) >= 1

    # department users cannot read stats at all
    worker = auth(client, "w1@x.org")
    assert (
        client.get("/api/stats/municipality", headers=worker).status_code == 404
    )
    assert client.get("/api/stats/platform", headers=admin).status_code == 404


def test_platform_stats_lists_municipalities_and_unanswered(
    client, db, world, cron_headers
):
    from app.services.metrics import TZ

    headers = auth(client, "w1@x.org")
    convo = client.post("/api/conversations", headers=headers).json()["id"]
    client.post(
        f"/api/chat/{convo}/messages",
        json={"content": "What is the capital of France?"},
        headers=headers,
    )
    today = datetime.now(TZ).date().isoformat()
    client.post(f"/api/cron/metrics-rollup?day={today}", headers=cron_headers)

    sysadmin = auth(client, "sys@x.org")
    stats = client.get("/api/stats/platform?range_days=30", headers=sysadmin).json()
    assert {b["name"] for b in stats["breakdown"]} == {"City One", "City Two"}
    assert stats["kpis"]["unanswered"] >= 1
    assert stats["kpis"]["unanswered_pct"] > 0
    assert stats["unanswered_questions"][0]["question"] == (
        "What is the capital of France?"
    )


def test_invalid_range_rejected(client, world):
    admin = auth(client, "a1@x.org")
    assert (
        client.get("/api/stats/municipality?range_days=5", headers=admin).status_code
        == 422
    )


def test_weekly_digest_sends_and_skips(client, db, world, cron_headers, outbox):
    from app.models import User

    headers = auth(client, "w1@x.org")
    client.post(
        "/api/board-items",
        data={
            "title": "Fresh guide",
            "category_id": str(world["cat"].id),
            "destination": "global",
            "link_url": "https://example.org/fresh",
        },
        headers=headers,
    )
    # one user opts out — must not receive anything
    opted_out = db.query(User).filter(User.email == "w2@x.org").one()
    opted_out.digest_enabled = False
    db.commit()

    r = client.post("/api/cron/weekly-digest", headers=cron_headers)
    assert r.status_code == 200
    assert r.json()["sent"] >= 1

    bodies = [f.read_text(encoding="utf-8") for f in outbox.glob("*.json")]
    assert any("Fresh guide" in b for b in bodies)
    assert not any("w2@x.org" in b for b in bodies)

    # same week → no second send
    assert client.post("/api/cron/weekly-digest", headers=cron_headers).json() == {
        "skipped": "already_ran"
    }


def test_archive_purge_deletes_expired_departments(client, db, world, cron_headers):
    from app.models import Department

    dept = world["d1"]
    dept_id = dept.id
    dept.status = "archived"
    dept.archive_expires_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()

    r = client.post("/api/cron/archive-purge", headers=cron_headers)
    assert r.status_code == 200
    assert r.json()["departments_purged"] == 1
    db.expire_all()
    assert db.query(Department).filter(Department.id == dept_id).count() == 0


def test_archive_purge_keeps_unexpired(client, db, world, cron_headers):
    from app.models import Department

    dept = world["d1"]
    dept.status = "archived"
    dept.archive_expires_at = datetime.now(UTC) + timedelta(days=30)
    db.commit()

    r = client.post("/api/cron/archive-purge", headers=cron_headers)
    assert r.json()["departments_purged"] == 0
    assert db.query(Department).filter(Department.id == dept.id).count() == 1


def test_cron_run_records_written(client, db, world, cron_headers):
    from app.models import CronRun

    client.post("/api/cron/archive-purge", headers=cron_headers)
    run = db.query(CronRun).filter(CronRun.job == "archive-purge").one()
    assert run.finished_at is not None and run.counts is not None
