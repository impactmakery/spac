import pytest


@pytest.fixture()
def outbox(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "outbox_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def world(db):
    """Two municipalities with admins + a department each, one system admin."""
    from app.core.security import hash_password
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    d2 = Department(municipality=m2, name="Health")
    sysadmin = User(
        email="root@x.org", role="system_admin", status="active",
        password_hash=hash_password("root-password-1"), name="Root",
    )
    a1 = User(
        email="admin1@x.org", role="municipality_admin", municipality=m1, status="active",
        password_hash=hash_password("admin-password-1"), name="Admin One",
    )
    a2 = User(
        email="admin2@x.org", role="municipality_admin", municipality=m2, status="active",
        password_hash=hash_password("admin-password-1"), name="Admin Two",
    )
    db.add_all([m1, m2, d1, d2, sysadmin, a1, a2])
    db.commit()
    return {"m1": m1, "m2": m2, "d1": d1, "d2": d2, "sys": sysadmin, "a1": a1, "a2": a2}


def auth(client, email, password="admin-password-1"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_muni_admin_invites_department_user(client, db, world, outbox):
    headers = auth(client, "admin1@x.org")
    r = client.post(
        "/api/invitations",
        json={
            "email": "new@x.org",
            "role": "department_user",
            "department_ids": [str(world["d1"].id)],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert list(outbox.glob("*.json")), "invite email sent"

    from app.models import AuditLog, User

    invited = db.query(User).filter(User.email == "new@x.org").one()
    assert invited.status == "invited"
    assert invited.municipality_id == world["m1"].id
    assert db.query(AuditLog).filter(AuditLog.action == "invitation.create").count() == 1


def test_muni_admin_cannot_invite_to_other_municipality_department(client, world):
    headers = auth(client, "admin1@x.org")
    r = client.post(
        "/api/invitations",
        json={
            "email": "new2@x.org",
            "role": "department_user",
            "department_ids": [str(world["d2"].id)],
        },
        headers=headers,
    )
    assert r.status_code == 404


def test_muni_admin_cannot_invite_admin_role(client, world):
    headers = auth(client, "admin1@x.org")
    r = client.post(
        "/api/invitations",
        json={"email": "new3@x.org", "role": "municipality_admin", "department_ids": []},
        headers=headers,
    )
    assert r.status_code == 403


def test_sysadmin_invites_municipality_admin(client, db, world, outbox):
    headers = auth(client, "root@x.org", "root-password-1")
    r = client.post(
        "/api/invitations",
        json={
            "email": "newadmin@x.org",
            "role": "municipality_admin",
            "municipality_id": str(world["m2"].id),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text

    from app.models import User

    invited = db.query(User).filter(User.email == "newadmin@x.org").one()
    assert invited.role == "municipality_admin"
    assert invited.municipality_id == world["m2"].id


def test_duplicate_email_blocked_409(client, world):
    headers = auth(client, "admin1@x.org")
    body = {
        "email": "dup@x.org",
        "role": "department_user",
        "department_ids": [str(world["d1"].id)],
    }
    assert client.post("/api/invitations", json=body, headers=headers).status_code == 201
    assert client.post("/api/invitations", json=body, headers=headers).status_code == 409
    # also blocked for an existing active user
    body["email"] = "admin1@x.org"
    assert client.post("/api/invitations", json=body, headers=headers).status_code == 409


def test_department_user_cannot_invite(client, db, world):
    from app.core.security import hash_password
    from app.models import User

    u = User(
        email="plain@x.org", role="department_user", municipality=world["m1"],
        status="active", password_hash=hash_password("plain-password-1"),
    )
    db.add(u)
    db.commit()
    headers = auth(client, "plain@x.org", "plain-password-1")
    r = client.post(
        "/api/invitations",
        json={"email": "z@x.org", "role": "department_user",
              "department_ids": [str(world["d1"].id)]},
        headers=headers,
    )
    assert r.status_code == 404


def test_resend_regenerates_token(client, db, world, outbox):
    headers = auth(client, "admin1@x.org")
    r = client.post(
        "/api/invitations",
        json={"email": "re@x.org", "role": "department_user",
              "department_ids": [str(world["d1"].id)]},
        headers=headers,
    )
    inv_id = r.json()["id"]
    from app.models import Invitation

    first_hash = db.get(Invitation, __import__("uuid").UUID(inv_id)).token_hash
    r2 = client.post(f"/api/invitations/{inv_id}/resend", headers=headers)
    assert r2.status_code == 200
    db.expire_all()
    assert db.get(Invitation, __import__("uuid").UUID(inv_id)).token_hash != first_hash
    assert len(list(outbox.glob("*.json"))) == 2


def test_resend_scope_enforced_404(client, world):
    headers1 = auth(client, "admin1@x.org")
    r = client.post(
        "/api/invitations",
        json={"email": "scoped@x.org", "role": "department_user",
              "department_ids": [str(world["d1"].id)]},
        headers=headers1,
    )
    inv_id = r.json()["id"]
    headers2 = auth(client, "admin2@x.org")
    assert client.post(f"/api/invitations/{inv_id}/resend", headers=headers2).status_code == 404


def test_me_departments(client, db, world):
    from app.core.security import hash_password
    from app.models import User

    u = User(
        email="deptuser@x.org", role="department_user", municipality=world["m1"],
        status="active", password_hash=hash_password("plain-password-1"),
        departments=[world["d1"]],
    )
    db.add(u)
    db.commit()
    headers = auth(client, "deptuser@x.org", "plain-password-1")
    r = client.get("/api/users/me/departments", headers=headers)
    assert r.status_code == 200
    assert r.json() == [{"id": str(world["d1"].id), "name": "Welfare"}]
