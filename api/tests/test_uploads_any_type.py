"""Any file type may be uploaded — a deliberate product decision.

The security control that replaces the old whitelist is narrower and different:
nothing outside a known-safe set is ever *rendered* in the browser. Uploading an
HTML file is allowed; having it execute against another user's session on our own
origin is not. These tests hold that line.
"""

import io


def test_any_extension_is_accepted_on_the_board():
    from app.services.uploads import validate_upload

    for filename, content in [
        ("notes.txt", b"plain text"),
        ("data.csv", b"a,b,c"),
        ("screenshot.png", b"\x89PNG\r\n\x1a\n"),
        ("archive.zip", b"PK\x03\x04"),
        ("tool.exe", b"MZ\x90\x00"),
        ("script.sh", b"#!/bin/sh\necho hi"),
        ("no_extension", b"whatever"),
    ]:
        ext, content_type = validate_upload(
            filename, content, "application/octet-stream", allow_any=True
        )
        assert isinstance(content_type, str) and content_type


def test_the_curated_surfaces_keep_their_guard():
    """Only the board is unrestricted. The knowledge base and department areas
    exist to hold material the assistant reads, so a binary in them is dead
    weight — and the whitelist there is still a real control."""
    from fastapi import HTTPException

    from app.services.uploads import validate_upload

    for filename, content in [("tool.exe", b"MZ"), ("archive.zip", b"PK\x03\x04")]:
        try:
            validate_upload(filename, content, "application/octet-stream")
        except HTTPException as e:
            assert e.status_code == 415
        else:
            raise AssertionError(f"{filename} was accepted outside the board")

    # a renamed file is caught by its contents, not trusted on its extension
    try:
        validate_upload("fake.pdf", b"not a pdf at all", "application/pdf")
    except HTTPException as e:
        assert e.status_code == 415
    else:
        raise AssertionError("a renamed file passed the curated check")

    # and the legitimate ones still work, including the newly-allowed images
    assert validate_upload("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")[0] == "png"
    assert validate_upload("notes.txt", b"hello", "text/plain")[0] == "txt"


def test_size_cap_still_applies():
    from fastapi import HTTPException

    from app.services.uploads import MAX_UPLOAD_BYTES, validate_upload

    try:
        validate_upload("big.txt", b"0" * (MAX_UPLOAD_BYTES + 1), "text/plain")
    except HTTPException as e:
        assert e.status_code == 413
    else:
        raise AssertionError("oversize upload was accepted")


def test_only_known_safe_types_are_rendered_in_the_browser():
    """The whole point: an uploaded file must not be able to run script on our
    origin. HTML and SVG both can, so neither is ever served inline."""
    from app.services.uploads import is_inline_safe, validate_upload

    assert is_inline_safe("application/pdf")
    assert is_inline_safe("image/png")

    for filename, content in [
        ("payload.html", b"<script>alert(1)</script>"),
        ("payload.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>"),
        ("payload.xhtml", b"<html/>"),
        ("tool.exe", b"MZ"),
    ]:
        _, content_type = validate_upload(
            filename, content, "text/html", allow_any=True
        )
        assert not is_inline_safe(content_type), filename


def test_browser_declared_type_is_never_trusted():
    """The declared type is attacker-supplied and decides how the file is served.
    Claiming application/pdf must not get an HTML file rendered."""
    from app.services.uploads import is_inline_safe, validate_upload

    _, content_type = validate_upload(
        "payload.html", b"<script>", "application/pdf", allow_any=True
    )
    assert not is_inline_safe(content_type)


def test_local_file_route_downloads_anything_it_will_not_render(client, tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.storage import LocalDiskProvider

    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))
    provider = LocalDiskProvider()
    provider.put("board/x/payload.html", b"<script>alert(1)</script>", "text/html")

    url = provider.download_url("board/x/payload.html", "payload.html",
                                content_type="text/html")
    res = client.get(url)
    assert res.status_code == 200
    assert res.headers["content-disposition"].startswith("attachment")
    assert res.headers["content-type"].startswith("application/octet-stream")
    assert res.headers["x-content-type-options"] == "nosniff"


def test_local_file_route_still_previews_a_pdf(client, tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.storage import LocalDiskProvider

    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))
    provider = LocalDiskProvider()
    provider.put("kb/x/doc.pdf", b"%PDF-1.4 ...", "application/pdf")

    url = provider.download_url("kb/x/doc.pdf", "doc.pdf", content_type="application/pdf")
    res = client.get(url)
    assert res.status_code == 200
    assert res.headers["content-disposition"].startswith("inline")
    assert res.headers["content-type"].startswith("application/pdf")


# --- extraction of the newly-allowed types -----------------------------------


def test_plain_text_and_csv_are_read():
    from app.rag.extract import extract_text

    assert "Budget" in extract_text(b"Budget guidance 2026", "txt")
    assert "Chairs" in extract_text(b"Item,Cost\nChairs,1200", "csv")


def test_hebrew_text_survives_legacy_encodings():
    from app.rag.extract import extract_text

    assert "שלום" in extract_text("שלום עולם".encode(), "txt")
    assert "שלום" in extract_text("שלום עולם".encode("cp1255"), "txt")


def test_an_unreadable_type_does_not_fail_the_upload():
    """A zip has no text we can read. The post keeps its title and description,
    and the file is still downloadable — that is not an indexing failure."""
    from app.services.uploads import is_extractable

    assert not is_extractable("zip")
    assert not is_extractable("exe")
    assert is_extractable("png")
    assert is_extractable("txt")


def test_image_ocr_returns_text_or_empty_never_raises():
    from PIL import Image

    from app.rag.extract import extract_text

    buf = io.BytesIO()
    Image.new("RGB", (200, 60), "white").save(buf, format="PNG")
    assert isinstance(extract_text(buf.getvalue(), "png"), str)
