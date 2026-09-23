from pathlib import Path

import pytest

from app.ingestion.parser import PDFParser


FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


# The fixture has 4 physical pages; page 1 is deliberately left with no
# extractable text, mirroring the cover page of the real annual report.


@pytest.fixture
def pages():
    return PDFParser().parse(FIXTURE)


def test_parser_extracts_pages(pages):
    assert pages, "parser returned no pages"
    assert all(page.text.strip() for page in pages)


def test_page_numbers_are_physical_and_may_have_gaps(pages):
    """
    Page numbers are physical and 1-based. Pages with no extractable
    text are skipped, so numbering can start above 1 and contain gaps.

    This is the parser's real contract. The previous test asserted
    pages[0].page_number == 1, which fails on any PDF whose first page
    is an image-only cover.
    """

    numbers = [page.page_number for page in pages]

    assert numbers == [2, 3, 4]

    assert numbers == sorted(numbers)
    assert len(set(numbers)) == len(numbers)


def test_text_free_pages_are_dropped_silently(pages):
    """
    Documents the known risk: a scanned or image-only page yields no
    text and disappears from the index with no warning. If page-level
    OCR or a warning is added later, this test should be updated.
    """

    assert len(pages) == 3
    assert 1 not in [page.page_number for page in pages]


def test_page_text_is_preserved(pages):
    by_number = {page.page_number: page.text for page in pages}

    assert "Alpha section." in by_number[2]
    assert "123,456" in by_number[3]


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        PDFParser().parse(Path("does_not_exist.pdf"))


def test_non_pdf_raises(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("plain text")

    with pytest.raises(ValueError):
        PDFParser().parse(bad)
