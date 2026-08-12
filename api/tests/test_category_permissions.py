"""Who may add, rename and remove a category.

Adding one used to need a system admin, so people filed things under whichever
category already existed — worse for finding them later than the occasional
surplus category. Anyone may now add and correct one.

Renaming, merging and removing stay with a system admin: they are the ones
with a screen for it, and those acts reach every municipality's board.
"""

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Municipality, User

    pw = hash_password("category-pw-11")
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
    r = client.post("/api/auth/login", json={"email": email, "password": "category-pw-11"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("email", ["root@x.org", "admin@x.org", "worker@x.org"])
def test_anyone_may_add_a_category(client, world, email):
    r = client.post(
        "/api/categories",
        json={"name_he": f"קטגוריה {email}", "name_en": f"Category {email}"},
        headers=auth(client, email),
    )
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("email", ["admin@x.org", "worker@x.org"])
def test_renaming_stays_with_a_system_admin(client, world, email):
    """Only they have a screen for it, and a rename relabels every board."""
    cid = client.post(
        "/api/categories", json={"name_he": "שם קיים"},
        headers=auth(client, "root@x.org"),
    ).json()["id"]

    r = client.patch(f"/api/categories/{cid}", json={"name_he": "שם אחר"},
                     headers=auth(client, email))
    assert r.status_code in (403, 404), email


@pytest.mark.parametrize("email", ["admin@x.org", "worker@x.org"])
def test_only_a_system_admin_may_delete(client, world, email):
    """The irreversible act, on something every municipality shares."""
    cid = client.post(
        "/api/categories", json={"name_he": "לא למחיקה"},
        headers=auth(client, "root@x.org"),
    ).json()["id"]

    r = client.delete(f"/api/categories/{cid}", headers=auth(client, email))
    assert r.status_code in (403, 404), email
    # and it is still there
    names = [c["name_he"] for c in
             client.get("/api/categories", headers=auth(client, email)).json()]
    assert "לא למחיקה" in names


@pytest.mark.parametrize("email", ["admin@x.org", "worker@x.org"])
def test_only_a_system_admin_may_merge(client, world, email):
    """Merging moves every post from one category to another — destructive in
    the same way deleting is, so it keeps the same guard."""
    headers = auth(client, "root@x.org")
    a = client.post("/api/categories", json={"name_he": "אחת"}, headers=headers).json()["id"]
    b = client.post("/api/categories", json={"name_he": "שתיים"}, headers=headers).json()["id"]

    r = client.post(f"/api/categories/{a}/merge-into/{b}", headers=auth(client, email))
    assert r.status_code in (403, 404), email


def test_a_system_admin_can_still_delete(client, world):
    headers = auth(client, "root@x.org")
    cid = client.post(
        "/api/categories", json={"name_he": "זמנית"}, headers=headers
    ).json()["id"]
    assert client.delete(f"/api/categories/{cid}", headers=headers).status_code == 200


def test_a_duplicate_name_is_still_refused_whoever_adds_it(client, world):
    """Opening this up must not open the door to two categories reading alike."""
    client.post("/api/categories", json={"name_he": "כפילות"},
                headers=auth(client, "root@x.org"))
    r = client.post("/api/categories", json={"name_he": "כפילות"},
                    headers=auth(client, "worker@x.org"))
    assert r.status_code == 409


def test_who_changed_it_is_recorded(client, db, world):
    """Anyone may edit, so the audit trail is what makes that safe."""
    from app.models import AuditLog, User

    cid = client.post("/api/categories", json={"name_he": "מעקב"},
                      headers=auth(client, "worker@x.org")).json()["id"]
    worker = db.query(User).filter_by(email="worker@x.org").one()
    actions = [
        row.action
        for row in db.query(AuditLog).filter(AuditLog.actor_id == worker.id).all()
    ]
    assert "category.create" in actions
    assert cid
