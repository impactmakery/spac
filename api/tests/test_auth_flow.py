import json
from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def _fresh_limiters():
    from app.core.ratelimit import forgot_limiter, login_limiter

    login_limiter.reset("testclient")
    forgot_limiter.reset("testclient")
    yield
    login_limiter.reset("testclient")
    forgot_limiter.reset("testclient")


@pytest.fixture()
def outbox(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "outbox_dir", str(tmp_path))
    return tmp_path


def make_user(db, email="alice@example.org", password="secret-password-1", **kw):
    from app.core.security import hash_password
    from app.models import Municipality, User

    muni = kw.pop("municipality", None) or Municipality(name="Demo City")
    defaults = dict(
        email=email,
        password_hash=hash_password(password),
        name="Alice",
        role="department_user",
        municipality=muni,
        status="active",
    )
    defaults.update(kw)
    user = User(**defaults)
    db.add_all([muni, user])
    db.commit()
    return user


def read_link_token(outbox_dir, param="token"):
    files = sorted(outbox_dir.glob("*.json"))
    assert files, "no email in outbox"
    html = json.loads(files[-1].read_text(encoding="utf-8"))["html"]
    marker = f"{param}="
    start = html.index(marker) + len(marker)
    end = start
    while end < len(html) and html[end] not in "\"'&<":
        end += 1
    return html[start:end]


def test_login_success_and_payload(client, db):
    user = make_user(db)
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "secret-password-1"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.org"
    assert body["user"]["role"] == "department_user"
    db.refresh(user)
    assert user.last_login_at is not None


def test_login_wrong_password_generic_401(client, db):
    make_user(db)
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "nope-nope-nope"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"
    r2 = client.post(
        "/api/auth/login", json={"email": "ghost@example.org", "password": "nope-nope-nope"}
    )
    assert r2.status_code == 401
    assert r2.json()["detail"] == "invalid_credentials"


def test_login_inactive_user_401(client, db):
    make_user(db, status="inactive")
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "secret-password-1"}
    )
    assert r.status_code == 401


def test_login_rate_limited_429(client, db):
    make_user(db)
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "a@b.c", "password": "wrong-wrong-1"})
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "secret-password-1"}
    )
    assert r.status_code == 429


def test_forgot_always_ok_and_reset_cycle(client, db, outbox):
    from app.core.security import create_access_token

    user = make_user(db)
    old_jwt = create_access_token(user)

    assert client.post("/api/auth/forgot", json={"email": "ghost@example.org"}).status_code == 200
    assert not list(outbox.glob("*.json"))

    assert client.post("/api/auth/forgot", json={"email": "alice@example.org"}).status_code == 200
    raw = read_link_token(outbox)

    r = client.post("/api/auth/reset", json={"token": raw, "password": "new-password-123"})
    assert r.status_code == 200

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "alice@example.org", "password": "secret-password-1"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "alice@example.org", "password": "new-password-123"},
        ).status_code
        == 200
    )
    # old sessions invalidated
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {old_jwt}"})
    assert r.status_code in (401, 404)
    # token single-use
    assert (
        client.post(
            "/api/auth/reset", json={"token": raw, "password": "another-password-1"}
        ).status_code
        == 410
    )


def test_reset_rejects_short_password(client, db, outbox):
    make_user(db)
    client.post("/api/auth/forgot", json={"email": "alice@example.org"})
    raw = read_link_token(outbox)
    r = client.post("/api/auth/reset", json={"token": raw, "password": "short"})
    assert r.status_code == 422


def test_invite_info_and_accept_cycle(client, db):
    from app.core.security import hash_token, new_raw_token
    from app.models import Department, Invitation, Municipality, User

    muni = Municipality(name="Demo City")
    dept = Department(municipality=muni, name="Welfare")
    inviter = User(
        email="admin@example.org", role="municipality_admin", municipality=muni,
        status="active", name="Admin",
    )
    invited = User(
        email="bob@example.org", role="department_user", municipality=muni, status="invited"
    )
    db.add_all([muni, dept, inviter, invited])
    db.flush()
    raw = new_raw_token()
    inv = Invitation(
        email="bob@example.org",
        role="department_user",
        municipality_id=muni.id,
        department_ids=[str(dept.id)],
        token_hash=hash_token(raw),
        invited_by=inviter.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(inv)
    db.commit()

    info = client.get(f"/api/auth/invite-info?token={raw}")
    assert info.status_code == 200
    assert info.json() == {
        "email": "bob@example.org",
        "inviter_name": "Admin",
        "municipality_name": "Demo City",
        "department_names": ["Welfare"],
        "role": "department_user",
    }

    r = client.post(
        "/api/auth/accept-invite",
        json={"token": raw, "name": "Bob", "password": "bobs-password-1", "language": "en"},
    )
    assert r.status_code == 200

    login = client.post(
        "/api/auth/login", json={"email": "bob@example.org", "password": "bobs-password-1"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["department_ids"] == [str(dept.id)]

    # single use
    assert client.get(f"/api/auth/invite-info?token={raw}").status_code == 410


def test_expired_invite_410(client, db):
    from app.core.security import hash_token, new_raw_token
    from app.models import Invitation, Municipality, User

    muni = Municipality(name="M")
    invited = User(email="c@x.org", role="department_user", municipality=muni, status="invited")
    db.add_all([muni, invited])
    db.flush()
    raw = new_raw_token()
    db.add(
        Invitation(
            email="c@x.org",
            role="department_user",
            municipality_id=muni.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db.commit()
    assert client.get(f"/api/auth/invite-info?token={raw}").status_code == 410
    assert client.get("/api/auth/invite-info?token=garbage").status_code == 404


def test_change_password_cycle(client, db):
    from app.core.security import create_access_token

    user = make_user(db)
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    bad = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-wrong-1", "new_password": "brand-new-pass-1"},
        headers=headers,
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/auth/change-password",
        json={"current_password": "secret-password-1", "new_password": "brand-new-pass-1"},
        headers=headers,
    )
    assert ok.status_code == 200
    fresh = ok.json()["access_token"]

    # old token dead, fresh works
    assert client.get("/api/users/me", headers=headers).status_code == 401
    assert (
        client.get("/api/users/me", headers={"Authorization": f"Bearer {fresh}"}).status_code
        == 200
    )
