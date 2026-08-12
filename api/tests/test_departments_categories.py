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

    # anyone may add one — that is what the publish form needs — but the
    # destructive operations stay with a system admin
    assert (
        client.post(
            "/api/categories",
            json={"name_he": "x", "name_en": "x"},
            headers=muni_headers,
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/api/categories/{c1}", json={"name_he": "y"}, headers=muni_headers
        ).status_code
        == 404
    )

    r = client.post(f"/api/categories/{c1}/merge-into/{c2}", headers=sys_headers)
    assert r.status_code == 200
    # the merged-away category is gone and its target remains; the extra one
    # added above is beside the point here
    names = {c["name_en"] for c in client.get("/api/categories", headers=sys_headers).json()}
    assert "Tools" not in names
    assert "Guides" in names


# --- Hebrew-only categories ---------------------------------------------------
# The users are Hebrew-speaking; the English name exists for whoever runs the
# platform, so it must never be the thing that blocks creating a category.


def test_category_can_be_created_with_hebrew_only(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    res = client.post("/api/categories", json={"name_he": "חינוך"}, headers=sys_headers)
    assert res.status_code == 201, res.text
    assert res.json()["name_he"] == "חינוך"
    assert res.json()["name_en"] is None


def test_blank_english_is_stored_as_absent_not_empty(client, world):
    """Empty strings would collide on the unique index the moment a second
    category was created without an English name."""
    sys_headers = auth(client, "root@x.org", "root-password-1")
    first = client.post(
        "/api/categories", json={"name_he": "רווחה", "name_en": "   "}, headers=sys_headers
    )
    second = client.post(
        "/api/categories", json={"name_he": "תברואה", "name_en": ""}, headers=sys_headers
    )
    assert first.status_code == 201 and second.status_code == 201, second.text
    assert first.json()["name_en"] is None and second.json()["name_en"] is None


def test_duplicate_hebrew_name_is_still_refused(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    client.post("/api/categories", json={"name_he": "תקציב"}, headers=sys_headers)
    again = client.post("/api/categories", json={"name_he": "תקציב"}, headers=sys_headers)
    assert again.status_code == 409


def test_english_name_can_be_added_later(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    created = client.post(
        "/api/categories", json={"name_he": "סביבה"}, headers=sys_headers
    )
    cid = created.json()["id"]
    res = client.patch(
        f"/api/categories/{cid}",
        json={"name_he": "סביבה", "name_en": "Environment"},
        headers=sys_headers,
    )
    assert res.status_code == 200
    assert res.json()["name_en"] == "Environment"


# --- colour and deletion ------------------------------------------------------


def test_category_colour_round_trips(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    created = client.post(
        "/api/categories",
        json={"name_he": "חינוך", "color": "teal"},
        headers=sys_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["color"] == "teal"

    cid = created.json()["id"]
    changed = client.patch(
        f"/api/categories/{cid}",
        json={"name_he": "חינוך", "color": "amber"},
        headers=sys_headers,
    )
    assert changed.json()["color"] == "amber"

    # clearing it returns to the colour derived from the id
    cleared = client.patch(
        f"/api/categories/{cid}", json={"name_he": "חינוך"}, headers=sys_headers
    )
    assert cleared.json()["color"] is None


def test_colour_must_be_a_palette_key_not_a_style(client, world):
    """The value reaches a stylesheet, so it is a slug and nothing else."""
    sys_headers = auth(client, "root@x.org", "root-password-1")
    for bad in ["#ff0000", "red; background:url(x)", "RED", "a" * 40]:
        res = client.post(
            "/api/categories",
            json={"name_he": f"בדיקה {bad[:4]}", "color": bad},
            headers=sys_headers,
        )
        assert res.status_code == 422, f"{bad!r} was accepted"


def test_unused_category_can_be_deleted(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    cid = client.post(
        "/api/categories", json={"name_he": "זמני"}, headers=sys_headers
    ).json()["id"]

    assert client.delete(f"/api/categories/{cid}", headers=sys_headers).status_code == 200
    assert all(c["id"] != cid for c in client.get("/api/categories", headers=sys_headers).json())


def test_category_in_use_is_refused_rather_than_orphaning_posts(client, db, world):
    """Posts reference categories, so deleting one in use would either fail at
    the database or leave posts pointing at nothing. Merge exists for that."""
    from app.models import BoardItem

    sys_headers = auth(client, "root@x.org", "root-password-1")
    cid = client.post(
        "/api/categories", json={"name_he": "בשימוש"}, headers=sys_headers
    ).json()["id"]

    import uuid as _uuid

    db.add(BoardItem(title="A post", category_id=_uuid.UUID(cid), scope="global"))
    db.commit()

    res = client.delete(f"/api/categories/{cid}", headers=sys_headers)
    assert res.status_code == 409
    assert res.json()["detail"] == "category_in_use"


def test_only_a_system_admin_may_delete(client, world):
    sys_headers = auth(client, "root@x.org", "root-password-1")
    cid = client.post(
        "/api/categories", json={"name_he": "מוגנת"}, headers=sys_headers
    ).json()["id"]

    muni = auth(client, "admin1@x.org")
    assert client.delete(f"/api/categories/{cid}", headers=muni).status_code in (403, 404)
