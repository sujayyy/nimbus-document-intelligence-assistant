from pathlib import Path

from app.ingestion.parser import PDFParser


def test_parser_extracts_pages():

    pdf_path = Path("test.pdf")

    parser = PDFParser()

    pages = parser.parse(pdf_path)

    assert len(pages) > 0

    assert pages[0].page_number == 1

    assert pages[0].text.strip()