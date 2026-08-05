import pytest

from app.rag.smalltalk import classify


@pytest.mark.parametrize(
    "text,expected",
    [
        ("hi", "greeting"),
        ("Hello!", "greeting"),
        ("  hey  ", "greeting"),
        ("good morning", "greeting"),
        ("שלום", "greeting"),
        ("היי", "greeting"),
        ("בוקר טוב", "greeting"),
        ("thanks", "thanks"),
        ("Thank you very much!", "thanks"),
        ("תודה רבה", "thanks"),
        ("what can you do?", "capabilities"),
        ("Who are you", "capabilities"),
        ("מי אתה", "capabilities"),
        # real questions must never be swallowed as pleasantries
        ("hi, when is waste collected?", None),
        ("What does the Tomorrow Program support?", None),
        ("מתי מתבצע פינוי האשפה?", None),
        ("thanks for the guide, where is the budget form?", None),
        ("", None),
    ],
)
def test_classification(text, expected):
    assert classify(text) == expected


def test_greeting_answers_conversationally_and_is_not_logged(client, db):
    """A greeting must not read as a failure, and must not pollute the
    unanswered-questions panel that drives knowledge base curation."""
    from app.core.security import hash_password
    from app.models import Municipality, UnansweredQuestion, User

    muni = Municipality(name="City")
    user = User(
        email="greeter@x.org", role="department_user", municipality=muni,
        status="active", password_hash=hash_password("greeting-pass-1"), name="G",
    )
    db.add_all([muni, user])
    db.commit()

    token = client.post(
        "/api/auth/login",
        json={"email": "greeter@x.org", "password": "greeting-pass-1"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    convo = client.post("/api/conversations", headers=headers).json()["id"]

    r = client.post(f"/api/chat/{convo}/messages", json={"content": "hi"}, headers=headers)
    answer = r.text
    assert "does not cover" not in answer
    assert "Tomorrow Agent" in answer
    assert db.query(UnansweredQuestion).count() == 0

    # Hebrew greeting answers in Hebrew
    r = client.post(
        f"/api/chat/{convo}/messages", json={"content": "שלום"}, headers=headers
    )
    assert "סוכן מחר" in r.text
    assert db.query(UnansweredQuestion).count() == 0

    # a genuine unanswerable question still logs, as before
    client.post(
        f"/api/chat/{convo}/messages",
        json={"content": "What is the population of Reykjavik?"},
        headers=headers,
    )
    assert db.query(UnansweredQuestion).count() == 1


def test_answer_language_rule_is_explicit_in_the_prompt():
    """An English question over Hebrew sources must still answer in English."""
    from app.rag.generation import SYSTEM_PROMPT

    assert "language of the QUESTION" in SYSTEM_PROMPT
    assert "never the language of the" in SYSTEM_PROMPT
