"""Starter questions must only name documents the reader may open.

A title here is not neutral: the one that exposed this named a tender
rejection, a committee and a programme belonging to another municipality.
The questions were built from the four most recently uploaded documents on
the whole platform, with no permission filter, so every user saw whatever
had been uploaded last anywhere — and clicking it always answered "not
covered", because retrieval was filtered correctly even though the
suggestion was not.

Reported from production: a דיר אל אסד administrator was offered
"מה כתוב במסמך «דחייה 26.4 עיתון — ...»?", a קריית שמונה document.
"""

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import KbDocument, Municipality, User

    pw = hash_password("samples-pw-11")
    a = Municipality(name="דיר אל אסד")
    b = Municipality(name="קריית שמונה")
    db.add_all([a, b])
    db.flush()

    users = {
        "sys": User(email="s@x.org", role="system_admin", status="active",
                    password_hash=pw, name="Root", language="he"),
        "a_admin": User(email="a@x.org", role="municipality_admin", municipality=a,
                        status="active", password_hash=pw, name="A", language="he"),
        "a_user": User(email="au@x.org", role="department_user", municipality=a,
                       status="active", password_hash=pw, name="AU", language="he"),
        "b_admin": User(email="b@x.org", role="municipality_admin", municipality=b,
                        status="active", password_hash=pw, name="B", language="he"),
    }
    db.add_all(users.values())
    db.flush()

    def doc(title, scope, muni):
        d = KbDocument(title=title, filename="f.docx", storage_key="k", size_bytes=1,
                       content_type="application/octet-stream", status="indexed",
                       scope=scope, municipality_id=muni.id if muni else None,
                       uploader_id=users["sys"].id)
        db.add(d)
        return d

    # newest last, so an unfiltered "four most recent" would pick B's
    doc("מדריך משותף", "global", None)
    doc("נוהל דיר אל אסד", "municipality", a)
    for i in range(4):
        doc(f"דחייה {i} עיתון — קריית שמונה", "municipality", b)
    db.commit()
    return {"a": a, "b": b}


def auth(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "samples-pw-11"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def questions(client, email):
    r = client.get("/api/chat/sample-questions", headers=auth(client, email))
    assert r.status_code == 200
    return r.json()


def test_a_municipality_is_never_offered_another_ones_document(client, world):
    for email in ("a@x.org", "au@x.org"):
        asked = " ".join(questions(client, email))
        assert "קריית שמונה" not in asked, email
        assert "דחייה" not in asked, email


def test_it_offers_the_documents_they_can_actually_read(client, world):
    asked = " ".join(questions(client, "a@x.org"))
    assert "נוהל דיר אל אסד" in asked or "מדריך משותף" in asked


def test_a_clicked_question_is_answerable_rather_than_not_covered(client, db, world):
    """The point of the filter: the suggestion and the answer must agree.

    A question about an unreadable document could only ever come back "not
    covered" — the assistant behaving correctly while the interface wasted
    the person's time.
    """
    from app.models import KbDocument, User
    from app.services.kb_access import readable_kb_documents

    user = db.query(User).filter_by(email="au@x.org").one()
    readable = {
        d.title for d in db.query(KbDocument).filter(readable_kb_documents(user)).all()
    }
    for q in questions(client, "au@x.org"):
        named = q.split("«")[1].split("»")[0] if "«" in q else None
        if named is not None:
            assert named in readable, f"offered an unreadable document: {named}"


def test_a_municipality_with_no_documents_still_gets_something_to_ask(client, db, world):
    """Three of the seven municipalities sent empty folders."""
    from app.core.security import hash_password
    from app.models import Municipality, User

    empty = Municipality(name="חורפיש")
    db.add(empty)
    db.flush()
    db.add(User(email="empty@x.org", role="municipality_admin", municipality=empty,
                status="active", password_hash=hash_password("samples-pw-11"),
                name="E", language="he"))
    db.commit()

    asked = questions(client, "empty@x.org")
    # the shared library is readable by everyone, so they get that; never nothing
    assert asked
    assert "קריית שמונה" not in " ".join(asked)


def test_a_system_admin_still_sees_everything(client, world):
    asked = " ".join(questions(client, "s@x.org"))
    assert "דחייה" in asked
