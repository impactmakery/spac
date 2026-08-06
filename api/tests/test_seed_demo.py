"""The demo seed is what a pilot and a handover are shown, so it has to keep
working — and the permission boundary it advertises has to be real."""

import pytest


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def seeded(db, files_dir):
    from scripts.seed_demo import seed

    seed(db, index=True)
    return db


def _user(db, email):
    from sqlalchemy import func, select

    from app.models import User

    return db.scalar(select(User).where(func.lower(User.email) == email))


def test_seed_creates_the_advertised_dataset(seeded):
    from app.models import (
        BoardItem,
        Chunk,
        Department,
        DepartmentFile,
        KbDocument,
        Municipality,
    )

    db = seeded
    assert db.query(Municipality).count() == 2
    assert db.query(Department).count() == 5
    assert db.query(KbDocument).count() == 3
    assert db.query(BoardItem).count() == 3
    assert db.query(DepartmentFile).count() == 2

    # every source actually made it through the pipeline
    assert db.query(KbDocument).filter(KbDocument.status != "indexed").count() == 0
    assert db.query(DepartmentFile).filter(DepartmentFile.status != "indexed").count() == 0
    for visibility in ("global", "municipality", "department"):
        assert db.query(Chunk).filter(Chunk.visibility == visibility).count() > 0


def test_seed_is_idempotent(seeded, capsys):
    from app.models import Municipality
    from scripts.seed_demo import seed

    seed(seeded, index=False)
    assert "already present" in capsys.readouterr().out
    assert seeded.query(Municipality).count() == 2


def test_the_demo_permission_boundary_is_real(seeded):
    """The staffing figure lives only in Karmiel's education department. This is
    the scope-appendix acceptance item, shown in the product rather than only
    asserted in the retrieval unit tests."""
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    question = "כמה תקנים חדשים מקצה תוכנית כוח האדם של אגף החינוך?"
    [vec] = get_embedding_provider().embed([question])

    def ask(email):
        return retrieve(
            seeded, query_embedding=vec, user=_user(seeded, email), query_text=question
        )

    owner_hits = ask("education.karmiel@tomorrow-hub.org")
    assert owner_hits, "the owning department must be able to find its own file"
    assert any("ארבעה תקנים" in h.content for h in owner_hits)

    for outsider in (
        "welfare.nahariya@tomorrow-hub.org",  # other municipality entirely
        "education.nahariya@tomorrow-hub.org",  # same-named department, other muni
        "admin.nahariya@tomorrow-hub.org",  # admin of the other municipality
    ):
        assert not any("ארבעה תקנים" in h.content for h in ask(outsider)), outsider


def test_global_knowledge_reaches_every_user(seeded):
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    question = "Procurement above 150,000 NIS requires a tender under regulation 17.3"
    [vec] = get_embedding_provider().embed([question])
    for email in (
        "welfare.nahariya@tomorrow-hub.org",
        "education.karmiel@tomorrow-hub.org",
        "admin@tomorrow-hub.org",
    ):
        hits = retrieve(
            seeded, query_embedding=vec, user=_user(seeded, email), query_text=question
        )
        assert any("regulation 17.3" in h.content for h in hits), email


def test_municipality_board_content_stays_inside_its_municipality(seeded):
    from app.rag.embeddings import get_embedding_provider
    from app.rag.retrieval import retrieve

    question = "מתי פתוח מרכז המיחזור העירוני?"
    [vec] = get_embedding_provider().embed([question])

    def contents(email):
        return " ".join(
            h.content
            for h in retrieve(
                seeded, query_embedding=vec, user=_user(seeded, email), query_text=question
            )
        )

    assert "מרכז המיחזור" in contents("welfare.nahariya@tomorrow-hub.org")
    assert "מרכז המיחזור" not in contents("education.karmiel@tomorrow-hub.org")
