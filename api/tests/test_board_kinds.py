"""Posts, announcements, events and questions.

A kind says what sort of thing a post is, separately from what it carries: an
event can still have a file attached, an announcement can still carry a link.
Everything that existed before is a 'post', and the form still produces one by
default — so none of this changes what is already on a board.
"""

import io
import uuid

import pytest


@pytest.fixture()
def world(db):
    from app.core.security import hash_password
    from app.models import Category, Municipality, User

    pw = hash_password("kinds-password-1")
    muni = Municipality(name="City")
    cat = Category(name_he="כללי", name_en="General")
    db.add_all([muni, cat])
    db.flush()
    db.add_all(
        [
            User(email="a@x.org", role="department_user", municipality=muni,
                 status="active", password_hash=pw, name="Author"),
            User(email="b@x.org", role="department_user", municipality=muni,
                 status="active", password_hash=pw, name="Other"),
            User(email="c@x.org", role="municipality_admin", municipality=muni,
                 status="active", password_hash=pw, name="Admin"),
        ]
    )
    db.commit()
    return {"muni": muni, "cat": cat}


def auth(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "kinds-password-1"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def publish(client, headers, world, **extra):
    data = {
        "title": extra.pop("title", "Something"),
        "category_id": str(world["cat"].id),
        "destination": "municipality",
        **extra,
    }
    # A plain post still has to carry something; the other kinds are the words
    # themselves. Supplying a link here keeps each test about its own subject.
    if data.get("kind", "post") == "post" and "link_url" not in data:
        data["link_url"] = "https://example.org/thing"
    return client.post("/api/board-items", data=data, headers=headers)


def test_a_post_is_still_what_you_get_without_asking(client, world):
    r = publish(client, auth(client, "a@x.org"), world)
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "post"
    assert r.json()["event_at"] is None


@pytest.mark.parametrize("kind", ["post", "announcement", "question"])
def test_the_dateless_kinds_publish(client, world, kind):
    r = publish(client, auth(client, "a@x.org"), world, kind=kind)
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == kind


def test_an_event_keeps_its_date_time_and_place(client, world):
    r = publish(client, auth(client, "a@x.org"), world, kind="event",
                event_at="2026-09-15T14:30", event_location="חדר ישיבות, קומה 2")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "event"
    assert body["event_at"].startswith("2026-09-15T14:30")
    assert body["event_has_time"] is True
    assert body["event_location"] == "חדר ישיבות, קומה 2"


def test_a_date_without_an_hour_is_remembered_as_such(client, world):
    """Things are often announced as a day before the hour is settled, and
    showing everyone 00:00 would be inventing a detail nobody gave."""
    r = publish(client, auth(client, "a@x.org"), world, kind="event", event_at="2026-09-15")
    assert r.status_code == 201, r.text
    assert r.json()["event_has_time"] is False


def test_an_event_without_a_date_is_refused(client, world):
    """It could not appear among what is coming up, which is the point of one."""
    r = publish(client, auth(client, "a@x.org"), world, kind="event")
    assert r.status_code == 422
    assert r.json()["detail"] == "event_date_required"


def test_an_unreadable_date_is_refused_rather_than_guessed(client, world):
    r = publish(client, auth(client, "a@x.org"), world, kind="event", event_at="next tuesday")
    assert r.status_code == 422
    assert r.json()["detail"] == "invalid_event_date"


def test_an_unknown_kind_is_refused(client, world):
    r = publish(client, auth(client, "a@x.org"), world, kind="poll")
    assert r.status_code == 422


# --- accepting an answer ----------------------------------------------------


def _question_with_reply(client, world, asker="a@x.org", replier="b@x.org"):
    item = publish(client, auth(client, asker), world, kind="question",
                   title="How do I file this?").json()
    comment = client.post(
        f"/api/board-items/{item['id']}/comments",
        json={"body": "Like this."},
        headers=auth(client, replier),
    ).json()
    return item, comment


def test_the_asker_can_mark_the_reply_that_answered_it(client, world):
    item, comment = _question_with_reply(client, world)
    r = client.post(f"/api/board-items/{item['id']}/accept",
                    json={"comment_id": comment["id"]}, headers=auth(client, "a@x.org"))
    assert r.status_code == 200, r.text
    assert r.json()["accepted_comment_id"] == comment["id"]


def test_the_asker_can_change_their_mind(client, world):
    item, comment = _question_with_reply(client, world)
    headers = auth(client, "a@x.org")
    client.post(f"/api/board-items/{item['id']}/accept",
                json={"comment_id": comment["id"]}, headers=headers)
    r = client.post(f"/api/board-items/{item['id']}/accept",
                    json={"comment_id": None}, headers=headers)
    assert r.status_code == 200
    assert r.json()["accepted_comment_id"] is None


def test_nobody_else_may_decide_which_answer_is_right(client, world):
    """Not the replier, and not an administrator: whose question it is decides."""
    item, comment = _question_with_reply(client, world)
    for email in ("b@x.org", "c@x.org"):
        r = client.post(f"/api/board-items/{item['id']}/accept",
                        json={"comment_id": comment["id"]}, headers=auth(client, email))
        assert r.status_code == 404, email


def test_only_a_question_can_have_an_accepted_answer(client, world):
    item = publish(client, auth(client, "a@x.org"), world, kind="post").json()
    comment = client.post(f"/api/board-items/{item['id']}/comments",
                          json={"body": "hi"}, headers=auth(client, "b@x.org")).json()
    r = client.post(f"/api/board-items/{item['id']}/accept",
                    json={"comment_id": comment["id"]}, headers=auth(client, "a@x.org"))
    assert r.status_code == 422
    assert r.json()["detail"] == "not_a_question"


def test_a_comment_from_another_post_cannot_be_accepted(client, world):
    """It would point the answer at something nobody reading this can see."""
    item, _ = _question_with_reply(client, world)
    elsewhere = publish(client, auth(client, "a@x.org"), world, title="Other").json()
    stray = client.post(f"/api/board-items/{elsewhere['id']}/comments",
                        json={"body": "unrelated"}, headers=auth(client, "b@x.org")).json()
    r = client.post(f"/api/board-items/{item['id']}/accept",
                    json={"comment_id": stray["id"]}, headers=auth(client, "a@x.org"))
    assert r.status_code == 404


def test_deleting_the_accepted_reply_leaves_the_question_standing(client, db, world):
    """Unanswered again, rather than pointing at a comment that is gone."""
    from app.models import BoardItem

    item, comment = _question_with_reply(client, world)
    headers = auth(client, "a@x.org")
    client.post(f"/api/board-items/{item['id']}/accept",
                json={"comment_id": comment["id"]}, headers=headers)

    deleted = client.delete(
        f"/api/board-items/{item['id']}/comments/{comment['id']}",
        headers=auth(client, "b@x.org"),
    )
    assert deleted.status_code == 200, deleted.text

    db.expire_all()
    row = db.get(BoardItem, uuid.UUID(item["id"]))
    assert row is not None, "the question must survive its answer"
    assert row.accepted_comment_id is None


# --- what the assistant can find --------------------------------------------


def test_an_events_date_and_place_reach_the_assistant(client, db, world):
    """Asking when the training day is only works if the day is in the text,
    rather than sitting in a column nothing searches."""
    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    publish(client, auth(client, "a@x.org"), world, kind="event",
            title="Training day", event_at="2026-09-15T09:00",
            event_location="Community centre")
    run_pending_jobs(db)

    text = " ".join(c.content for c in db.query(Chunk).all())
    assert "2026-09-15" in text
    assert "Community centre" in text


def test_a_question_is_searchable_like_any_other_post(client, db, world):
    from app.models import Chunk
    from app.services.ingestion import run_pending_jobs

    publish(client, auth(client, "a@x.org"), world, kind="question",
            title="Parking permits", description="Who approves parking permits?")
    run_pending_jobs(db)

    text = " ".join(c.content for c in db.query(Chunk).all())
    assert "parking permits" in text.lower()


def test_a_kind_does_not_stop_a_post_carrying_a_file(client, world):
    """Kind is what a post is; the attachment is what it carries."""
    r = client.post(
        "/api/board-items",
        data={"title": "Agenda", "category_id": str(world["cat"].id),
              "destination": "municipality", "kind": "event",
              "event_at": "2026-10-01"},
        files={"file": ("agenda.txt", io.BytesIO(b"the agenda"), "text/plain")},
        headers=auth(client, "a@x.org"),
    )
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "event"
    assert r.json()["filename"] == "agenda.txt"
