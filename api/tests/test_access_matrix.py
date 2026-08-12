"""Permission matrix sweep: every role against every cross-scope resource.

Grows with each stage. A permission regression here must never merge (CI-gated).
"""

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import BoardItem, Category, Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d2 = Department(municipality=m2, name="Foreign Dept")
    cat = Category(name_he="כלים", name_en="Tools")
    pw = hash_password("matrix-password-1")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw)
    a1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
              status="active", password_hash=pw)
    u1 = User(email="u1@x.org", role="department_user", municipality=m1,
              status="active", password_hash=pw)
    u2 = User(email="u2@x.org", role="department_user", municipality=m2,
              status="active", password_hash=pw)
    db.add_all([m1, m2, d2, cat, sysadmin, a1, u1, u2])
    db.flush()
    # an item on City Two's municipality board, authored by its own member
    foreign_item = BoardItem(
        title="City Two only", description="private", category_id=cat.id,
        scope="municipality", municipality_id=m2.id, author_id=u2.id,
        link_url="https://example.org/x",
    )
    db.add(foreign_item)
    db.commit()
    return {"m2": m2, "d2": d2, "item2": foreign_item, "cat": cat}


def login(client, email):
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "matrix-password-1"}
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# (method, path-template, body, denied-roles → expected status)
CASES = [
    # system-admin-only surfaces
    ("GET", "/api/municipalities", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("POST", "/api/municipalities", {"name": "Nope"}, {"a1@x.org": 404, "u1@x.org": 404}),
    # Creating a category is deliberately open to everyone — the publish form
    # needs it mid-thought. Changing or removing one is not: those relabel or
    # remove something every municipality shares.
    ("PATCH", "/api/categories/{cat}", {"name_he": "x"},
     {"a1@x.org": 404, "u1@x.org": 404}),
    ("DELETE", "/api/categories/{cat}", None, {"a1@x.org": 404, "u1@x.org": 404}),
    # admin-only surfaces
    ("GET", "/api/admin/users", None, {"u1@x.org": 404}),
    ("GET", "/api/departments", None, {"u1@x.org": 404}),
    ("POST", "/api/invitations",
     {"email": "zz@x.org", "role": "department_user", "department_ids": []},
     {"u1@x.org": 404}),
    # cross-municipality resources (foreign department d2)
    ("PATCH", "/api/departments/{d2}", {"name": "X"}, {"a1@x.org": 404}),
    ("POST", "/api/departments/{d2}/archive", None, {"a1@x.org": 404}),
    # foreign municipality board item — existence must not leak (404, never 403)
    ("GET", "/api/board-items/{item2}", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("PATCH", "/api/board-items/{item2}",
     {"title": "hijack", "category_id": "{cat}"}, {"a1@x.org": 404, "u1@x.org": 404}),
    ("DELETE", "/api/board-items/{item2}", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("POST", "/api/board-items/{item2}/like", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("POST", "/api/board-items/{item2}/comments", {"body": "hi"},
     {"a1@x.org": 404, "u1@x.org": 404}),
    # foreign department content
    ("GET", "/api/departments/{d2}/files", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("GET", "/api/departments/{d2}/posts", None, {"a1@x.org": 404, "u1@x.org": 404}),
    ("POST", "/api/departments/{d2}/posts", {"body": "leak"},
     {"a1@x.org": 404, "u1@x.org": 404}),
]


def _fill(value, world):
    if isinstance(value, dict):
        return {k: _fill(v, world) for k, v in value.items()}
    if isinstance(value, str):
        return (
            value.replace("{d2}", str(world["d2"].id))
            .replace("{item2}", str(world["item2"].id))
            .replace("{cat}", str(world["cat"].id))
        )
    return value


@pytest.mark.parametrize("method,path,body,denials", CASES)
def test_denied_roles(client, world, method, path, body, denials):
    body = _fill(body, world)
    path = _fill(path, world)
    for email, expected in denials.items():
        headers = login(client, email)
        r = client.request(method, path, json=body, headers=headers)
        assert r.status_code == expected, (
            f"{email} {method} {path} → {r.status_code}, expected {expected}"
        )


@pytest.mark.parametrize("method,path,body,_", CASES)
def test_anonymous_401(client, world, method, path, body, _):
    path = _fill(path, world)
    r = client.request(method, path, json=_fill(body, world))
    assert r.status_code in (401, 403), f"anonymous {method} {path} → {r.status_code}"
