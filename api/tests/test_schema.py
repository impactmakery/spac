import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_identity_tables_exist(engine):
    tables = set(inspect(engine).get_table_names())
    assert {
        "municipalities",
        "departments",
        "users",
        "user_departments",
        "invitations",
        "password_reset_tokens",
        "audit_log",
    } <= tables


def test_user_department_roundtrip(db):
    from app.models import Department, Municipality, User

    muni = Municipality(name="Demo City")
    dept = Department(municipality=muni, name="Welfare")
    user = User(
        email="u@example.org",
        role="department_user",
        municipality=muni,
        departments=[dept],
    )
    db.add_all([muni, dept, user])
    db.commit()
    loaded = db.get(User, user.id)
    assert loaded is not None and loaded.departments[0].name == "Welfare"
    assert loaded.status == "invited" and loaded.token_version == 0


def test_active_department_name_unique_per_municipality(db):
    from app.models import Department, Municipality

    muni = Municipality(name="Demo City")
    db.add(muni)
    db.add(Department(municipality=muni, name="Welfare"))
    db.commit()
    db.add(Department(municipality=muni, name="welfare"))
    with pytest.raises(IntegrityError):
        db.commit()
