import pytest


@pytest.fixture()
def sysadmin_headers(client, db):
    from app.core.security import hash_password
    from app.models import User

    db.add(
        User(
            email="root@x.org", role="system_admin", status="active",
            password_hash=hash_password("root-password-1"), name="Root",
        )
    )
    db.commit()
    r = client.post(
        "/api/auth/login", json={"email": "root@x.org", "password": "root-password-1"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_list_rename(client, db, sysadmin_headers):
    r = client.post("/api/municipalities", json={"name": "City A"}, headers=sysadmin_headers)
    assert r.status_code == 201
    muni_id = r.json()["id"]

    assert (
        client.post(
            "/api/municipalities", json={"name": "city a"}, headers=sysadmin_headers
        ).status_code
        == 409
    )

    r = client.patch(
        f"/api/municipalities/{muni_id}", json={"name": "City B"}, headers=sysadmin_headers
    )
    assert r.status_code == 200

    rows = client.get("/api/municipalities", headers=sysadmin_headers).json()
    assert [m["name"] for m in rows] == ["City B"]
    assert rows[0]["user_count"] == 0 and rows[0]["department_count"] == 0

    from app.models import AuditLog

    assert (
        db.query(AuditLog).filter(AuditLog.action == "municipality.rename").count() == 1
    )


def test_deactivate_blocks_users_and_is_reversible(client, db, sysadmin_headers):
    from app.core.security import hash_password
    from app.models import Municipality, User

    muni = Municipality(name="City C")
    user = User(
        email="worker@x.org", role="department_user", municipality=muni, status="active",
        password_hash=hash_password("worker-password-1"),
    )
    db.add_all([muni, user])
    db.commit()

    login = client.post(
        "/api/auth/login", json={"email": "worker@x.org", "password": "worker-password-1"}
    )
    token = login.json()["access_token"]
    assert (
        client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )

    r = client.post(
        f"/api/municipalities/{muni.id}/deactivate", headers=sysadmin_headers
    )
    assert r.status_code == 200

    # existing session dead + login blocked
    assert (
        client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "worker@x.org", "password": "worker-password-1"},
        ).status_code
        == 401
    )

    r = client.post(
        f"/api/municipalities/{muni.id}/reactivate", headers=sysadmin_headers
    )
    assert r.status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "worker@x.org", "password": "worker-password-1"},
        ).status_code
        == 200
    )


def test_non_sysadmin_gets_404(client, db):
    from app.core.security import hash_password
    from app.models import Municipality, User

    muni = Municipality(name="City D")
    admin = User(
        email="ma@x.org", role="municipality_admin", municipality=muni, status="active",
        password_hash=hash_password("admin-password-1"),
    )
    db.add_all([muni, admin])
    db.commit()
    login = client.post(
        "/api/auth/login", json={"email": "ma@x.org", "password": "admin-password-1"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/municipalities", headers=headers).status_code == 404
    assert (
        client.post("/api/municipalities", json={"name": "X"}, headers=headers).status_code
        == 404
    )
