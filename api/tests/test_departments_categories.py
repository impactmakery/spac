import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    sysadmin = User(
        email="root@x.org", role="system_admin", status="active",
        password_hash=hash_password("root-password-1"), name="Root",
    )
    a1 = User(
        email="admin1@x.org", role="municipality_admin", municipality=m1, status="active",
        password_hash=hash_password("admin-password-1"),
    )
    a2 = User(
        email="admin2@x.org", role="municipality_admin", municipality=m2, status="active",
        password_hash=hash_password("admin-password-1"),
    )
    db.add_all([m1, m2, sysadmin, a1, a2])
    db.commit()
    return {"m1": m1, "m2": m2}


def auth(client, email, password="admin-password-1"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_department_lifecycle(client, db, world):
    headers = auth(client, "admin1@x.org")

    r = client.post("/api/departments", json={"name": "Welfare"}, headers=headers)
    assert r.status_code == 201
    dept_id = r.json()["id"]

    assert (
        client.post("/api/departments", json={"name": "welfare"}, headers=headers)
        .status_code
        == 409
    )

    r = client.patch(
        f"/api/departments/{dept_id}", json={"name": "Welfare 2"}, headers=headers
    )
    assert r.status_code == 200

    r = client.post(f"/api/departments/{dept_id}/archive", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"
    assert r.json()["archive_expires_at"] is not None

    assert client.get("/api/departments", headers=headers).json() == []
    archived = client.get("/api/departments?status=archived", headers=headers).json()
    assert [d["id"] for d in archived] == [dept_id]

    r = client.post(f"/api/departments/{dept_id}/restore", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "active" and r.json()["archive_expires_at"] is None


def test_department_cross_scope_404(client, db, world):
    headers1 = auth(client, "admin1@x.org")
    headers2 = auth(client, "admin2@x.org")
    dept_id = client.post(
        "/api/departments", json={"name": "Secret"}, headers=headers1
    ).json()["id"]
    assert (
        client.patch(
            f"/api/departments/{dept_id}", json={"name": "X"}, headers=headers2
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/departments/{dept_id}/archive", headers=headers2).status_code
        == 404
    )


def test_sysadmin_manages_departments_with_explicit_municipality(client, world):
    headers = auth(client, "root@x.org", "root-password-1")
    m1_id = str(world["m1"].id)
    r = client.post(
        "/api/departments",
        json={"name": "Edu", "municipality_id": m1_id},
        headers=headers,
    )
    assert r.status_code == 201
    rows = client.get(f"/api/departments?municipality_id={m1_id}", headers=headers).json()
    assert [d["name"] for d in rows] == ["Edu"]


def test_categories_crud_and_merge(client, db, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    muni_headers = auth(client, "admin1@x.org")

    r = client.post(
        "/api/categories",
        json={"name_he": "כלים", "name_en": "Tools"},
        headers=sys_headers,
    )
    assert r.status_code == 201
    c1 = r.json()["id"]
    c2 = client.post(
        "/api/categories",
        json={"name_he": "מדריכים", "name_en": "Guides"},
        headers=sys_headers,
    ).json()["id"]

    # any authed user can list
    rows = client.get("/api/categories", headers=muni_headers).json()
    assert {c["name_en"] for c in rows} == {"Tools", "Guides"}

    # only sysadmin mutates
    assert (
        client.post(
            "/api/categories",
            json={"name_he": "x", "name_en": "x"},
            headers=muni_headers,
        ).status_code
        == 404
    )

    r = client.post(f"/api/categories/{c1}/merge-into/{c2}", headers=sys_headers)
    assert r.status_code == 200
    rows = client.get("/api/categories", headers=sys_headers).json()
    assert [c["name_en"] for c in rows] == ["Guides"]
