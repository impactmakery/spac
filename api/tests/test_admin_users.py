import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d1 = Department(municipality=m1, name="Welfare")
    d1b = Department(municipality=m1, name="Health")
    d2 = Department(municipality=m2, name="Education")
    sysadmin = User(
        email="root@x.org", role="system_admin", status="active",
        password_hash=hash_password("root-password-1"), name="Root",
    )
    a1 = User(
        email="admin1@x.org", role="municipality_admin", municipality=m1, status="active",
        password_hash=hash_password("admin-password-1"), name="Admin One",
    )
    u1 = User(
        email="worker@x.org", role="department_user", municipality=m1, status="active",
        password_hash=hash_password("worker-password-1"), name="Worker",
        departments=[d1],
    )
    u2 = User(
        email="other@x.org", role="department_user", municipality=m2, status="active",
        password_hash=hash_password("worker-password-1"), name="Other",
    )
    db.add_all([m1, m2, d1, d1b, d2, sysadmin, a1, u1, u2])
    db.commit()
    return {"m1": m1, "m2": m2, "d1": d1, "d1b": d1b, "d2": d2, "u1": u1, "u2": u2,
            "a1": a1}


def auth(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_list_scoped_to_municipality(client, world):
    headers = auth(client, "admin1@x.org", "admin-password-1")
    rows = client.get("/api/admin/users", headers=headers).json()
    emails = {u["email"] for u in rows}
    assert "worker@x.org" in emails and "admin1@x.org" in emails
    assert "other@x.org" not in emails

    worker = next(u for u in rows if u["email"] == "worker@x.org")
    assert worker["departments"][0]["name"] == "Welfare"
    assert worker["has_zero_departments"] is False


def test_sysadmin_sees_all_and_filters(client, world):
    headers = auth(client, "root@x.org", "root-password-1")
    rows = client.get("/api/admin/users", headers=headers).json()
    assert {u["email"] for u in rows} >= {"worker@x.org", "other@x.org", "admin1@x.org"}
    rows = client.get(
        f"/api/admin/users?municipality_id={world['m2'].id}", headers=headers
    ).json()
    assert {u["email"] for u in rows} == {"other@x.org"}
    rows = client.get("/api/admin/users?search=worker", headers=headers).json()
    assert {u["email"] for u in rows} == {"worker@x.org"}


def test_set_departments_scope_and_zero_flag(client, db, world):
    headers = auth(client, "admin1@x.org", "admin-password-1")
    uid = str(world["u1"].id)

    r = client.put(
        f"/api/admin/users/{uid}/departments",
        json={"department_ids": [str(world["d1"].id), str(world["d1b"].id)]},
        headers=headers,
    )
    assert r.status_code == 200
    assert {d["name"] for d in r.json()["departments"]} == {"Welfare", "Health"}

    # other municipality's department → 404
    assert (
        client.put(
            f"/api/admin/users/{uid}/departments",
            json={"department_ids": [str(world["d2"].id)]},
            headers=headers,
        ).status_code
        == 404
    )

    r = client.put(
        f"/api/admin/users/{uid}/departments",
        json={"department_ids": []},
        headers=headers,
    )
    assert r.json()["has_zero_departments"] is True


def test_cross_municipality_user_404(client, world):
    headers = auth(client, "admin1@x.org", "admin-password-1")
    uid = str(world["u2"].id)
    assert (
        client.post(f"/api/admin/users/{uid}/deactivate", headers=headers).status_code
        == 404
    )


def test_deactivate_kills_session_reactivate_restores(client, db, world):
    admin_headers = auth(client, "admin1@x.org", "admin-password-1")
    worker_headers = auth(client, "worker@x.org", "worker-password-1")
    uid = str(world["u1"].id)

    assert client.get("/api/users/me", headers=worker_headers).status_code == 200
    r = client.post(f"/api/admin/users/{uid}/deactivate", headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/users/me", headers=worker_headers).status_code == 401

    r = client.post(f"/api/admin/users/{uid}/reactivate", headers=admin_headers)
    assert r.status_code == 200
    # same departments retained
    assert r.json()["departments"][0]["name"] == "Welfare"
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "worker@x.org", "password": "worker-password-1"},
        ).status_code
        == 200
    )


def test_promote_demote_and_last_admin_guard(client, db, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    muni_headers = auth(client, "admin1@x.org", "admin-password-1")
    uid = str(world["u1"].id)

    # municipality admin cannot promote
    assert (
        client.post(f"/api/admin/users/{uid}/promote", headers=muni_headers).status_code
        == 404
    )

    r = client.post(f"/api/admin/users/{uid}/promote", headers=sys_headers)
    assert r.status_code == 200 and r.json()["role"] == "municipality_admin"
    r = client.post(f"/api/admin/users/{uid}/demote", headers=sys_headers)
    assert r.status_code == 200 and r.json()["role"] == "department_user"

    # sysadmin cannot demote themselves
    from app.models import User

    root = db.query(User).filter(User.email == "root@x.org").one()
    assert (
        client.post(f"/api/admin/users/{root.id}/demote", headers=sys_headers).status_code
        == 409
    )


def test_department_user_gets_404_on_admin_endpoints(client, world):
    headers = auth(client, "worker@x.org", "worker-password-1")
    assert client.get("/api/admin/users", headers=headers).status_code == 404
