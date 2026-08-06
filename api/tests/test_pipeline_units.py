import io

import pytest

# ---------- upload validation ----------


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _docx_bytes(text="שלום עולם. Budget guidance for 2026.") -> bytes:
    import docx

    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_validate_upload_accepts_known_types():
    from app.services.uploads import validate_upload

    ext, ct = validate_upload("Doc.PDF", _pdf_bytes(), "application/pdf")
    assert (ext, ct) == ("pdf", "application/pdf")
    ext, _ = validate_upload("word.docx", _docx_bytes(), "application/octet-stream")
    assert ext == "docx"


def test_validate_upload_rejects_bad_extension_and_magic():
    from fastapi import HTTPException

    from app.services.uploads import validate_upload

    with pytest.raises(HTTPException) as e:
        validate_upload("script.exe", b"MZ....", "application/octet-stream")
    assert e.value.status_code == 415

    # extension says pdf but bytes are not a pdf
    with pytest.raises(HTTPException) as e:
        validate_upload("fake.pdf", b"not a pdf at all", "application/pdf")
    assert e.value.status_code == 415


def test_validate_upload_rejects_oversize():
    from fastapi import HTTPException

    from app.services.uploads import MAX_UPLOAD_BYTES, validate_upload

    big = b"%PDF-" + b"0" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(HTTPException) as e:
        validate_upload("big.pdf", big, "application/pdf")
    assert e.value.status_code == 413


# ---------- chunking ----------


def test_chunk_text_bounds_and_overlap():
    from app.rag.chunking import chunk_text, token_len

    text = " ".join(f"word{i}" for i in range(3000))
    chunks = chunk_text(text, max_tokens=800, overlap=150)
    assert len(chunks) > 1
    for c in chunks:
        assert token_len(c) <= 800
    # consecutive chunks share content (overlap)
    assert chunks[0][-40:] != chunks[1][-40:]
    assert any(w in chunks[1] for w in chunks[0].split()[-30:])


def test_chunk_text_short_input_single_chunk():
    from app.rag.chunking import chunk_text

    assert chunk_text("hello world") == ["hello world"]
    assert chunk_text("   ") == []


# ---------- embeddings ----------


def test_fake_embeddings_deterministic_unit_norm():
    import math

    from app.rag.embeddings import get_embedding_provider

    provider = get_embedding_provider()
    assert type(provider).__name__ == "FakeEmbeddings"  # no OPENAI_API_KEY in tests
    [a1], [a2] = provider.embed(["שלום"]), provider.embed(["שלום"])
    [b] = provider.embed(["something else"])
    assert a1 == a2 and a1 != b
    assert len(a1) == 1536
    assert abs(math.sqrt(sum(x * x for x in a1)) - 1.0) < 1e-6


# ---------- extraction ----------


def test_extract_docx_pptx_xlsx_pdf():
    from app.rag.extract import extract_text

    assert "Budget guidance" in extract_text(_docx_bytes(), "docx")

    import pptx

    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Quarterly plan"
    buf = io.BytesIO()
    prs.save(buf)
    assert "Quarterly plan" in extract_text(buf.getvalue(), "pptx")

    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["Item", "Cost"])
    wb.active.append(["Chairs", 1200])
    buf = io.BytesIO()
    wb.save(buf)
    text = extract_text(buf.getvalue(), "xlsx")
    assert "Chairs" in text and "1200" in text

    # blank pdf extracts to empty-ish, but must not raise
    assert isinstance(extract_text(_pdf_bytes(), "pdf"), str)


def test_extract_corrupt_raises():
    from app.rag.extract import ExtractionError, extract_text

    with pytest.raises(ExtractionError):
        extract_text(b"garbage bytes", "docx")


# ---------- structure-aware chunking ----------


def test_chunks_break_at_paragraph_boundaries():
    """A chunk that ends mid-sentence embeds poorly and reads badly when cited."""
    from app.rag.chunking import chunk_text, token_len

    paragraphs = [f"Paragraph {i}. " + " ".join(f"word{j}" for j in range(120))
                  for i in range(12)]
    chunks = chunk_text("\n\n".join(paragraphs), max_tokens=400, overlap=60)

    assert len(chunks) > 1
    for c in chunks:
        assert token_len(c) <= 400
        # every chunk starts at a paragraph start, never mid-sentence
        assert c.startswith("Paragraph")


def test_title_is_prepended_to_every_chunk():
    from app.rag.chunking import chunk_text

    body = "\n\n".join(f"Section {i} body text here." for i in range(5))
    chunks = chunk_text(body, max_tokens=20, overlap=5, title="Waste Guidelines")
    assert len(chunks) > 1
    assert all(c.startswith("Waste Guidelines") for c in chunks)
    # the title costs budget but must never displace content
    joined = " ".join(chunks)
    assert all(f"Section {i}" in joined for i in range(5))


def test_overlap_carries_context_across_the_seam():
    from app.rag.chunking import chunk_text

    paragraphs = [f"Block{i} " + " ".join(["filler"] * 40) for i in range(8)]
    chunks = chunk_text("\n\n".join(paragraphs), max_tokens=200, overlap=80)
    assert len(chunks) > 1
    # the start of a later chunk repeats the end of the previous one
    first_blocks = {line.split()[0] for line in chunks[0].split("\n\n")}
    second_blocks = {line.split()[0] for line in chunks[1].split("\n\n")}
    assert first_blocks & second_blocks


def test_single_oversized_block_is_still_split():
    from app.rag.chunking import chunk_text, token_len

    wall = " ".join(f"word{i}" for i in range(2000))  # no paragraph breaks at all
    chunks = chunk_text(wall, max_tokens=300, overlap=50)
    assert len(chunks) > 1
    assert all(token_len(c) <= 300 for c in chunks)


def test_short_document_stays_one_chunk():
    from app.rag.chunking import chunk_text

    assert chunk_text("A short procedure note.") == ["A short procedure note."]
    assert chunk_text("   ") == []
