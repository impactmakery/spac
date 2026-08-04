"""Permission matrix sweep: every role against every cross-scope resource.

Grows with each stage. A permission regression here must never merge (CI-gated).
"""

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Department, Municipality, User

    m1 = Municipality(name="City One")
    m2 = Municipality(name="City Two")
    d2 = Department(municipality=m2, name="Foreign Dept")
    pw = hash_password("matrix-password-1")
    sysadmin = User(email="sys@x.org", role="system_admin", status="active",
                    password_hash=pw)
    a1 = User(email="a1@x.org", role="municipality_admin", municipality=m1,
              status="active", password_hash=pw)
    u1 = User(email="u1@x.org", role="department_user", municipality=m1,
              status="active", password_hash=pw)
    db.add_all([m1, m2, d2, sysadmin, a1, u1])
    db.commit()
    return {"m2": m2, "d2": d2}


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
    ("POST", "/api/categories", {"name_he": "x", "name_en": "y"},
     {"a1@x.org": 404, "u1@x.org": 404}),
    # admin-only surfaces
    ("GET", "/api/admin/users", None, {"u1@x.org": 404}),
    ("GET", "/api/departments", None, {"u1@x.org": 404}),
    ("POST", "/api/invitations",
     {"email": "zz@x.org", "role": "department_user", "department_ids": []},
     {"u1@x.org": 404}),
    # cross-municipality resources (foreign department d2)
    ("PATCH", "/api/departments/{d2}", {"name": "X"}, {"a1@x.org": 404}),
    ("POST", "/api/departments/{d2}/archive", None, {"a1@x.org": 404}),
]


@pytest.mark.parametrize("method,path,body,denials", CASES)
def test_denied_roles(client, world, method, path, body, denials):
    path = path.replace("{d2}", str(world["d2"].id))
    for email, expected in denials.items():
        headers = login(client, email)
        r = client.request(method, path, json=body, headers=headers)
        assert r.status_code == expected, (
            f"{email} {method} {path} → {r.status_code}, expected {expected}"
        )


@pytest.mark.parametrize("method,path,body,_", CASES)
def test_anonymous_401(client, world, method, path, body, _):
    path = path.replace("{d2}", str(world["d2"].id))
    r = client.request(method, path, json=body)
    assert r.status_code in (401, 403), f"anonymous {method} {path} → {r.status_code}"
