from pathlib import Path

import pymupdf

from app.schemas.documents import PageText


class PDFParser:

    def parse(self, pdf_path: Path) -> list[PageText]:
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are supported.")

        pages: list[PageText] = []

        with pymupdf.open(pdf_path) as document:
            for page_index, page in enumerate(document):
                text = page.get_text("text", sort=True).strip()

                if not text:
                    continue

                pages.append(
                    PageText(
                        page_number=page_index + 1,
                        text=text,
                    )
                )

        if not pages:
            raise ValueError(
                "No extractable text was found in the PDF."
            )

        return pages