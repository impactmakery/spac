from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


def _make_user(db, **kw):
    from app.core.security import hash_password
    from app.models import Municipality, User

    muni = Municipality(name="Demo City")
    defaults = dict(
        email="a@example.org",
        password_hash=hash_password("secret-password"),
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


def _protected_client(engine):
    from app.core.db import get_db
    from app.core.security import get_current_user
    from app.main import create_app

    app = create_app()

    @app.get("/whoami")
    def whoami(user=Depends(get_current_user)) -> dict:
        return {"id": str(user.id), "role": user.role}

    def override():
        with sessionmaker(bind=engine)() as session:
            yield session

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_password_hash_roundtrip():
    from app.core.security import hash_password, verify_password

    h = hash_password("secret-password")
    assert h != "secret-password"
    assert verify_password("secret-password", h)
    assert not verify_password("wrong", h)


def test_jwt_claims(db):
    from app.core.security import create_access_token, decode_token

    user = _make_user(db)
    claims = decode_token(create_access_token(user))
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "department_user"
    assert claims["tv"] == 0
    assert claims["muni"] == str(user.municipality_id)
    assert claims["depts"] == []


def test_protected_route_and_token_version_kill(db, engine):
    from app.core.security import create_access_token

    user = _make_user(db)
    client = _protected_client(engine)
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/whoami", headers=headers).status_code == 200

    user.token_version += 1
    db.commit()
    assert client.get("/whoami", headers=headers).status_code == 401


def test_inactive_user_rejected(db, engine):
    from app.core.security import create_access_token

    user = _make_user(db)
    token = create_access_token(user)
    user.status = "inactive"
    db.commit()
    client = _protected_client(engine)
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_missing_or_garbage_token(db, engine):
    client = _protected_client(engine)
    assert client.get("/whoami").status_code in (401, 403)
    assert client.get("/whoami", headers={"Authorization": "Bearer junk"}).status_code == 401
