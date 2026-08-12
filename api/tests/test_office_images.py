"""An Office file whose content is pictures must not index as its title alone.

Text extraction only sees text runs. A slide deck exported from a design tool,
or a photographed page pasted into Word, carries its words in images — so the
assistant saw a filename and nothing else. Four documents in the first real
corpus were exactly that, three of them belonging to one municipality with
only ten documents in total.

These exercise which images we choose to read and when, not how well Tesseract
reads them: the binary is not installed on every developer machine, and its
accuracy is not ours to assert.
"""

import io
import zipfile

import pytest


def office_file(images: dict[str, int], prefix: str = "ppt/media/") -> bytes:
    """A minimal Office zip: name -> size in bytes of each embedded image."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        for name, size in images.items():
            z.writestr(f"{prefix}{name}", b"\x89PNG" + b"\0" * max(0, size - 4))
    return buf.getvalue()


@pytest.fixture()
def read_images(monkeypatch):
    """Record which embedded images were handed to OCR."""
    seen: list[int] = []

    def fake_image(content: bytes) -> str:
        seen.append(len(content))
        return f"words from a {len(content)} byte image"

    monkeypatch.setattr("app.rag.extract._image", fake_image)
    return seen


def test_pictures_are_read_when_the_document_says_almost_nothing(read_images):
    from app.rag.extract import _with_embedded_images

    content = office_file({"image1.png": 500_000})
    out = _with_embedded_images(content, "القائد لا يعد بالهدوء")

    assert "words from" in out
    assert "القائد" in out, "the original text must survive alongside"
    assert read_images


def test_a_document_with_real_text_is_left_alone(read_images):
    """OCR'ing the illustrations of a text-rich report is minutes for nothing."""
    from app.rag.extract import MIN_CHARS_OFFICE, _with_embedded_images

    content = office_file({"image1.png": 500_000})
    text = "א" * (MIN_CHARS_OFFICE + 1)

    assert _with_embedded_images(content, text) == text
    assert read_images == []


def test_logos_and_icons_are_skipped(read_images):
    """Municipal decks repeat a crest on every slide; reading it forty times
    costs minutes and returns nothing."""
    from app.rag.extract import OCR_MIN_IMAGE_BYTES, _office_images

    _office_images(office_file({
        "logo.png": OCR_MIN_IMAGE_BYTES - 1,
        "slide.png": OCR_MIN_IMAGE_BYTES + 1,
    }))
    assert len(read_images) == 1


def test_only_so_many_images_are_read_per_document(read_images):
    from app.rag.extract import OCR_MAX_EMBEDDED_IMAGES, _office_images

    many = {f"img{i:03}.png": 500_000 for i in range(OCR_MAX_EMBEDDED_IMAGES + 10)}
    _office_images(office_file(many))
    assert len(read_images) == OCR_MAX_EMBEDDED_IMAGES


@pytest.mark.parametrize("prefix", ["word/media/", "ppt/media/", "xl/media/"])
def test_every_office_format_keeps_its_pictures_somewhere_we_look(read_images, prefix):
    from app.rag.extract import _office_images

    _office_images(office_file({"image1.png": 500_000}, prefix=prefix))
    assert len(read_images) == 1


def test_non_images_in_the_media_folder_are_ignored(read_images):
    """Embedded video and audio live beside the pictures."""
    from app.rag.extract import _office_images

    _office_images(office_file({"clip.mp4": 900_000, "photo.jpg": 900_000}))
    assert len(read_images) == 1


def test_a_corrupt_file_costs_the_document_nothing():
    """This is a bonus pass over a document that already extracted; a failure
    here must not take away the little text it had."""
    from app.rag.extract import _office_images, _with_embedded_images

    assert _office_images(b"not a zip at all") == ""
    assert _with_embedded_images(b"not a zip at all", "title") == "title"


def test_ocr_failing_on_one_image_does_not_lose_the_others(monkeypatch):
    from app.rag.extract import _office_images

    def flaky(content: bytes) -> str:
        if len(content) > 600_000:
            raise RuntimeError("bad image")
        return "readable"

    monkeypatch.setattr("app.rag.extract._image", flaky)
    out = _office_images(office_file({"a.png": 900_000, "b.png": 500_000}))
    assert "readable" in out


# --- OCR languages ---------------------------------------------------------
#
# Two of the seven municipalities are Arabic-speaking towns. The container
# shipped with Hebrew and English packs only, so every scanned or picture-based
# Arabic document read as nothing at all — OCR running correctly and
# recognising no words, which looks exactly like a document that has none.


def test_arabic_is_among_the_languages_we_read():
    from app.rag.extract import _languages

    assert "ara" in _languages(), "an Arab municipality's documents would be unreadable"


def test_hebrew_and_english_are_still_read():
    from app.rag.extract import _languages

    langs = _languages()
    assert "heb" in langs
    assert "eng" in langs


def test_the_language_list_is_configuration(monkeypatch):
    """Another deployment serves other communities; this should not need a code change."""
    from app.core.config import get_settings
    from app.rag.extract import _languages

    monkeypatch.setattr(get_settings(), "ocr_languages", "heb+eng+rus")
    assert _languages() == "heb+eng+rus"


def test_an_empty_setting_falls_back_rather_than_breaking_ocr(monkeypatch):
    from app.core.config import get_settings
    from app.rag.extract import _languages

    monkeypatch.setattr(get_settings(), "ocr_languages", "")
    assert _languages() == "heb+eng"


def test_every_configured_language_has_a_package_in_the_dockerfile():
    """A language Tesseract has no pack for makes it fail, not degrade."""
    from pathlib import Path

    from app.core.config import get_settings

    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    for lang in get_settings().ocr_languages.split("+"):
        if lang == "eng":
            continue  # ships with the base tesseract-ocr package
        assert f"tesseract-ocr-{lang}" in dockerfile, f"no apt package for {lang}"
