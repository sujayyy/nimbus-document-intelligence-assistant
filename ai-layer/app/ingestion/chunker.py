from uuid import uuid4

from transformers import AutoTokenizer

from app.config import settings
from app.schemas.documents import DocumentChunk, PageText


class TokenChunker:

    def __init__(
        self,
        model_name: str = settings.embedding_model,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def chunk_pages(
        self,
        pages: list[PageText],
        document_id: str,
    ) -> list[DocumentChunk]:

        chunks: list[DocumentChunk] = []

        for page in pages:
            page_chunks = self._chunk_page(page, document_id)
            chunks.extend(page_chunks)

        return chunks

    def _chunk_page(
        self,
        page: PageText,
        document_id: str,
    ) -> list[DocumentChunk]:

        token_ids = self.tokenizer.encode(
            page.text,
            add_special_tokens=False,
        )

        if not token_ids:
            return []

        page_chunks: list[DocumentChunk] = []

        start = 0
        chunk_index = 0

        step = self.chunk_size - self.chunk_overlap

        while start < len(token_ids):

            end = min(
                start + self.chunk_size,
                len(token_ids),
            )

            chunk_token_ids = token_ids[start:end]

            chunk_text = self.tokenizer.decode(
                chunk_token_ids,
                skip_special_tokens=True,
            ).strip()

            if chunk_text:
                page_chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid4()),
                        document_id=document_id,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    )
                )

                chunk_index += 1

            if end >= len(token_ids):
                break

            start += step

        return page_chunks