"""RAG grounding acceptance test (scope appendix, Quality & Security).

30 fixed questions: 20 answerable from seeded documents (each must cite the
correct source) and 10 that must return the not-covered reply — including a
cross-department leak question whose answer exists only in another department.

The answerable set exists in two phrasings:

* ANSWERABLE_LEXICAL — shares vocabulary with the source, so it holds with the
  offline lexical embeddings too. Always runs.
* ANSWERABLE_SEMANTIC — natural paraphrases that only real (multilingual)
  embeddings can match. Runs when OPENAI_API_KEY is configured, which is the
  CI-nightly configuration the appendix asks for.

The unanswerable set and the cross-department leak test always run: those are
the security acceptance items and must hold regardless of embedding quality.
"""

import os
import uuid

import pytest

requires_real_embeddings = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="paraphrase matching requires real embeddings (set OPENAI_API_KEY)",
)

# (question, expected source key) — natural paraphrases
ANSWERABLE_SEMANTIC = [
    ("What are the waste collection days for households?", "waste"),
    ("Which neighbourhoods are covered by the recycling scheme?", "waste"),
    ("How should residents dispose of bulky furniture items?", "waste"),
    ("What is the annual budget planning cycle for municipalities?", "budget"),
    ("When must departments submit their budget proposals?", "budget"),
    ("Who approves the final municipal budget allocation?", "budget"),
    ("What training is offered to new program coordinators?", "training"),
    ("How many training days are required in the first year?", "training"),
    ("Which topics does the coordinator onboarding cover?", "training"),
    ("What accessibility standards apply to municipal buildings?", "accessibility"),
    ("Who is responsible for accessibility compliance audits?", "accessibility"),
    ("What is the deadline for accessibility retrofitting works?", "accessibility"),
    ("מהם ימי פינוי האשפה בשכונות?", "waste_he"),
    ("איך מדווחים על מפגע ברחוב?", "waste_he"),
    ("מהו תהליך אישור תקציב שנתי ברשות?", "budget_he"),
    ("מתי מגישות המחלקות הצעות תקציב?", "budget_he"),
    ("What welfare intake procedure applies to new applicants?", "welfare"),
    ("How long does the welfare intake assessment take?", "welfare"),
    ("What digital tools are shared on the board for summaries?", "board_tool"),
    ("Which tool helps write meeting summaries quickly?", "board_tool"),
]

# Reduced offline set: near-verbatim questions, which is the most a lexical
# index can honestly answer. Every one of the eight sources is still covered,
# so the permission scopes stay exercised without an API key.
ANSWERABLE_LEXICAL = [
    ("Which days does household waste collection operate in neighbourhoods?", "waste"),
    ("When are recycling containers emptied?", "waste"),
    ("When does the annual budget planning cycle begin?", "budget"),
    ("Who approves the final budget allocation?", "budget"),
    ("How many training days are required during the first year of service?", "training"),
    ("Does onboarding training include procurement rules and reporting duties?", "training"),
    ("Which accessibility standards apply to municipal buildings?", "accessibility"),
    ("Who is responsible for accessibility compliance audits?", "accessibility"),
    ("מתי מתבצע פינוי האשפה?", "waste_he"),
    ("מתי מתחיל תהליך אישור תקציב שנתי?", "budget_he"),
    ("מתי המחלקות מגישות הצעות תקציב?", "budget_he"),
    ("What does the welfare intake procedure for new applicants begin with?", "welfare"),
    ("Which shared digital tool helps write meeting summaries?", "board_tool"),
]

UNANSWERABLE = [
    "What is the population of Reykjavik in 1970?",
    "Who won the football world cup in 1986?",
    "What is the boiling point of mercury at high altitude?",
    "How do I renew a passport in another country?",
    "What are the tax brackets for freelance photographers?",
    "Which programming language should I learn first?",
    "מה מזג האוויר מחר בטוקיו?",
    "כמה עולה כרטיס טיסה לרומא?",
    "What is the recipe for traditional sourdough bread?",
    # the leak question: answered only in a department the asker cannot see
    "How many new staffing roles does the education plan allocate?",
]

DOCUMENTS = {
    "waste": (
        "Household waste collection operates every Tuesday and Friday across all "
        "neighbourhoods. Recycling containers are emptied on Wednesday. Residents "
        "dispose of bulky furniture items by scheduling a collection through the "
        "municipal hotline at least three working days in advance."
    ),
    "budget": (
        "The annual budget planning cycle begins each November. Departments submit "
        "their budget proposals by the fifteenth of December. The municipal council "
        "approves the final budget allocation during its January session."
    ),
    "training": (
        "New program coordinators receive structured onboarding training covering "
        "community engagement, procurement rules, and reporting duties. Twelve "
        "training days are required during the first year of service."
    ),
    "accessibility": (
        "Municipal buildings follow national accessibility standards for entrances, "
        "signage, and service counters. The municipal engineer is responsible for "
        "accessibility compliance audits. Retrofitting works must complete before "
        "the statutory deadline in September."
    ),
    "waste_he": (
        "פינוי האשפה מתבצע בימי שלישי ושישי בכל השכונות. דיווח על מפגע ברחוב מתבצע "
        "דרך מוקד הרשות או באפליקציה העירונית, ומטופל בתוך שלושה ימי עבודה."
    ),
    "budget_he": (
        "תהליך אישור תקציב שנתי ברשות מתחיל בנובמבר. המחלקות מגישות הצעות תקציב עד "
        "אמצע דצמבר, ומליאת המועצה מאשרת את התקציב בישיבת ינואר."
    ),
    "welfare": (
        "The welfare intake procedure for new applicants begins with an eligibility "
        "screening interview. The intake assessment takes up to fourteen days, after "
        "which a case worker is assigned."
    ),
    "board_tool": (
        "A shared digital tool helps staff write meeting summaries quickly by turning "
        "recorded notes into structured minutes. Teams use it for council sessions."
    ),
}

LEAK_DOCUMENT = (
    "The education staffing plan allocates four new roles in September, funded from "
    "the departmental reserve."
)


@pytest.fixture()
def eval_world(db):
    """Seeds documents across every visibility scope plus one department-only
    document the asking user must never reach."""
    from app.core.security import hash_password
    from app.models import Chunk, Department, KbDocument, Municipality, User
    from app.rag.embeddings import get_embedding_provider

    muni = Municipality(name="Eval City")
    welfare = Department(municipality=muni, name="Welfare")
    education = Department(municipality=muni, name="Education")
    asker = User(
        email="asker@x.org", role="department_user", municipality=muni, status="active",
        password_hash=hash_password("eval-password-11"), name="Asker",
        departments=[welfare],
    )
    db.add_all([muni, welfare, education, asker])
    db.flush()

    sources: dict[str, uuid.UUID] = {}
    provider = get_embedding_provider()

    def seed(key: str, text: str, *, visibility: str, department=None) -> None:
        doc = KbDocument(
            title=f"{key} document",
            filename=f"{key}.docx",
            storage_key=f"kb/{key}",
            size_bytes=1,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            status="indexed",
            municipality_id=muni.id,
        )
        db.add(doc)
        db.flush()
        sources[key] = doc.id
        [vec] = provider.embed([text])
        db.add(
            Chunk(
                source_type="kb",
                source_id=doc.id,
                visibility=visibility,
                municipality_id=muni.id if visibility != "global" else None,
                department_id=department.id if department else None,
                content=text,
                embedding=vec,
            )
        )

    for key, text in DOCUMENTS.items():
        # spread across scopes so the eval exercises the permission filter too
        if key in ("waste", "budget", "waste_he", "budget_he"):
            seed(key, text, visibility="global")
        elif key in ("training", "accessibility", "board_tool"):
            seed(key, text, visibility="municipality")
        else:
            seed(key, text, visibility="department", department=welfare)

    seed("leak", LEAK_DOCUMENT, visibility="department", department=education)
    db.commit()
    return {"sources": sources, "asker": asker}


def _ask(client, headers, convo_id, question):
    import json

    r = client.post(
        f"/api/chat/{convo_id}/messages", json={"content": question}, headers=headers
    )
    assert r.status_code == 200, r.text
    tokens, citations = [], []
    for block in r.text.strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        event = lines[0].removeprefix("event: ")
        payload = json.loads(lines[1].removeprefix("data: "))
        if event == "token":
            tokens.append(payload)
        elif event == "citations":
            citations = payload
    return "".join(tokens), citations


@pytest.fixture()
def chat(client, eval_world):
    from app.routers.chat import chat_limiter

    chat_limiter._hits.clear()
    r = client.post(
        "/api/auth/login", json={"email": "asker@x.org", "password": "eval-password-11"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    convo_id = client.post("/api/conversations", headers=headers).json()["id"]
    return headers, convo_id


def _assert_cites(client, chat, eval_world, question, expected_key):
    headers, convo_id = chat
    answer, citations = _ask(client, headers, convo_id, question)
    assert citations, f"no citation for: {question}"
    expected_id = str(eval_world["sources"][expected_key])
    cited = [c["source_id"] for c in citations]
    assert expected_id in cited, f"{question!r} cited {cited}, expected {expected_key}"
    assert "does not cover" not in answer and "אינו מכסה" not in answer


@pytest.mark.parametrize("question,expected_key", ANSWERABLE_LEXICAL)
def test_answerable_questions_cite_the_right_source(
    chat, client, eval_world, question, expected_key
):
    _assert_cites(client, chat, eval_world, question, expected_key)


@requires_real_embeddings
@pytest.mark.parametrize("question,expected_key", ANSWERABLE_SEMANTIC)
def test_paraphrased_questions_cite_the_right_source(
    chat, client, eval_world, question, expected_key
):
    _assert_cites(client, chat, eval_world, question, expected_key)


@pytest.mark.parametrize("question", UNANSWERABLE)
def test_unanswerable_questions_return_not_covered(chat, client, question):
    headers, convo_id = chat
    answer, citations = _ask(client, headers, convo_id, question)
    assert citations == [], f"unexpected citations for: {question}"
    assert "does not cover" in answer or "אינו מכסה" in answer


def test_leak_question_never_reveals_other_department_content(chat, client, db):
    """Explicit acceptance item: the answer exists only in another department."""
    from app.models import UnansweredQuestion

    headers, convo_id = chat
    answer, citations = _ask(
        chat and client, headers, convo_id,
        "How many new staffing roles does the education plan allocate?",
    )
    assert "four new roles" not in answer
    assert "staffing plan allocates" not in answer
    assert citations == []
    assert db.query(UnansweredQuestion).count() >= 1
