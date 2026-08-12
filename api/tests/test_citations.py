"""The numbers in an answer must match the numbers under it.

The model is shown numbered passages and told to cite them. Those numbers are
the only thing connecting a sentence to the document it came from, so if the
prompt numbers passages one way and the citation list numbers sources another,
every marker in every answer is either off-by-something or points at nothing.
"""

import uuid

import pytest

from app.rag.retrieval import RetrievedChunk


def chunk(source_id: uuid.UUID, content: str = "text") -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid.uuid4(),
        content=content,
        source_type="kb",
        source_id=source_id,
        visibility="global",
        municipality_id=None,
        department_id=None,
        similarity=0.9,
        score=1.0,
    )


@pytest.fixture()
def docs():
    return [uuid.uuid4() for _ in range(3)]


def test_passages_from_one_document_share_its_number(docs):
    """A citation points at a document, not at a passage."""
    from app.rag.retrieval import source_numbers

    a, b, c = docs
    assert source_numbers([chunk(a), chunk(a), chunk(b), chunk(a), chunk(c)]) == [
        1, 1, 2, 1, 3
    ]


def test_the_prompt_and_the_citation_list_agree(db, docs):
    """The regression: 12 passages from 5 documents produced markers up to [12]
    against a list numbered [1]..[5]."""
    from app.core.security import hash_password
    from app.models import KbDocument, User
    from app.rag.generation import build_prompt
    from app.services.citations import build_citations

    uploader = User(email="c@x.org", role="system_admin", status="active",
                    password_hash=hash_password("citations-pw-1"), name="Root")
    db.add(uploader)
    db.flush()
    ids = []
    for i in range(3):
        doc = KbDocument(title=f"Document {i}", filename=f"d{i}.docx", storage_key=f"k{i}",
                         size_bytes=1, content_type="application/octet-stream",
                         uploader_id=uploader.id, status="indexed", scope="global")
        db.add(doc)
        db.flush()
        ids.append(doc.id)
    db.commit()

    # four passages, but only three documents — the second document supplied two
    chunks = [chunk(ids[0]), chunk(ids[1]), chunk(ids[1]), chunk(ids[2])]
    citations = build_citations(db, chunks)
    prompt = build_prompt("q", chunks, [])

    numbered = {c["index"] for c in citations}
    assert numbered == {1, 2, 3}
    # every marker the model is offered must exist in the list beneath it
    assert "[4]" not in prompt
    for n in numbered:
        assert f"[{n}]" in prompt
    assert [c["title"] for c in citations] == ["Document 0", "Document 1", "Document 2"]


def test_a_vanished_source_leaves_a_gap_rather_than_shifting(db, docs):
    """Renumbering after a deletion would silently point markers at the wrong
    document; a missing number is at least honest."""
    from app.core.security import hash_password
    from app.models import KbDocument, User
    from app.services.citations import build_citations

    uploader = User(email="c2@x.org", role="system_admin", status="active",
                    password_hash=hash_password("citations-pw-1"), name="Root")
    db.add(uploader)
    db.flush()
    doc = KbDocument(title="Still here", filename="d.docx", storage_key="k",
                     size_bytes=1, content_type="application/octet-stream",
                     uploader_id=uploader.id, status="indexed", scope="global")
    db.add(doc)
    db.commit()

    gone = uuid.uuid4()  # never existed: stands in for deleted between the two steps
    citations = build_citations(db, [chunk(gone), chunk(doc.id)])
    assert [c["index"] for c in citations] == [2]
    assert citations[0]["title"] == "Still here"
