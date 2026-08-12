"""Two different files must not arrive under one title.

The importer builds a title from the filename without its extension, so a
report saved as both .docx and .pdf landed on the same title twice. In the
library and in a citation those look like a duplicate of something that is not
one: two real, different documents, indistinguishable in a list.

Ten pairs came through the first municipal load that way.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from import_folders import title_for, titles_for  # noqa: E402


def test_one_file_keeps_a_clean_title():
    """Naming the format on everything would be noise on the common case."""
    folder = Path("/muni")
    assert titles_for([folder / "report.docx"], folder) == {
        folder / "report.docx": "report"
    }


def test_the_same_name_in_two_formats_is_told_apart():
    folder = Path("/muni")
    paths = [folder / "budget.pdf", folder / "budget.pptx"]
    titles = titles_for(paths, folder)

    assert titles[paths[0]] == "budget (PDF)"
    assert titles[paths[1]] == "budget (PPTX)"
    assert len(set(titles.values())) == 2


def test_the_subfolder_still_shows():
    """Where a passage came from is the reason the title is built at all."""
    folder = Path("/muni")
    paths = [folder / "plans" / "q1.pdf", folder / "plans" / "q1.xlsx"]
    titles = titles_for(paths, folder)

    assert titles[paths[0]] == "q1 — plans (PDF)"
    assert titles[paths[1]] == "q1 — plans (XLSX)"


def test_the_same_name_in_different_folders_is_already_distinct():
    """Those never collided; adding the format would be noise."""
    folder = Path("/muni")
    paths = [folder / "a" / "notes.docx", folder / "b" / "notes.docx"]
    titles = titles_for(paths, folder)

    assert titles[paths[0]] == "notes — a"
    assert titles[paths[1]] == "notes — b"


def test_a_real_collision_from_the_municipal_load():
    folder = Path("/kiryat")
    paths = [
        folder / "חירום" / "מספרים חיוניים.docx",
        folder / "חירום" / "מספרים חיוניים.pdf",
    ]
    titles = titles_for(paths, folder)
    assert titles[paths[0]] == "מספרים חיוניים — חירום (DOCX)"
    assert titles[paths[1]] == "מספרים חיוניים — חירום (PDF)"


def test_three_formats_of_one_document():
    folder = Path("/muni")
    paths = [folder / "x.pdf", folder / "x.docx", folder / "x.png"]
    titles = titles_for(paths, folder)
    assert len(set(titles.values())) == 3


@pytest.mark.parametrize("count", [1, 2, 5])
def test_no_folder_of_any_shape_produces_a_repeated_title(count):
    folder = Path("/muni")
    paths = [folder / f"doc.{ext}" for ext in ("pdf", "docx", "xlsx", "pptx", "png")][:count]
    titles = titles_for(paths, folder)
    assert len(set(titles.values())) == len(paths)


def test_title_for_is_unchanged_for_the_single_file_case():
    """The simple helper still exists and still does the simple thing."""
    folder = Path("/muni")
    assert title_for(folder / "sub" / "a.pdf", folder) == "a — sub"
