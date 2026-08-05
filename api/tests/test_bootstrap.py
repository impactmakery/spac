import pytest


@pytest.fixture()
def bootstrap_settings(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_email", "first@example.org")
    monkeypatch.setattr(settings, "bootstrap_admin_password", "bootstrap-pass-1")
    return settings


def test_creates_first_admin_on_empty_platform(db, bootstrap_settings):
    from app.models import User
    from app.services.bootstrap import bootstrap_first_admin

    assert bootstrap_first_admin(db) is True
    admin = db.query(User).one()
    assert admin.email == "first@example.org"
    assert admin.role == "system_admin" and admin.status == "active"


def test_never_runs_once_any_user_exists(db, bootstrap_settings):
    """The guard is 'no users at all', so it cannot resurrect a removed admin
    or add a second one to a live platform."""
    from app.core.security import hash_password
    from app.models import Municipality, User
    from app.services.bootstrap import bootstrap_first_admin

    muni = Municipality(name="City")
    db.add_all(
        [
            muni,
            User(
                email="someone@example.org",
                role="department_user",
                municipality=muni,
                status="active",
                password_hash=hash_password("existing-password-1"),
            ),
        ]
    )
    db.commit()

    assert bootstrap_first_admin(db) is False
    assert db.query(User).count() == 1


def test_skipped_without_configuration(db, monkeypatch):
    from app.core.config import get_settings
    from app.models import User
    from app.services.bootstrap import bootstrap_first_admin

    monkeypatch.setattr(get_settings(), "bootstrap_admin_email", "")
    assert bootstrap_first_admin(db) is False
    assert db.query(User).count() == 0


def test_rejects_a_weak_password(db, monkeypatch, bootstrap_settings):
    from app.models import User
    from app.services.bootstrap import bootstrap_first_admin

    monkeypatch.setattr(bootstrap_settings, "bootstrap_admin_password", "short")
    assert bootstrap_first_admin(db) is False
    assert db.query(User).count() == 0


def test_bootstrapped_admin_can_log_in(client, db, bootstrap_settings):
    from app.services.bootstrap import bootstrap_first_admin

    bootstrap_first_admin(db)
    r = client.post(
        "/api/auth/login",
        json={"email": "first@example.org", "password": "bootstrap-pass-1"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "system_admin"
