from dataclasses import dataclass


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    page_number: int
    chunk_index: int
    text: str


@dataclass
class RetrievedChunk:
    chunk: DocumentChunk
    score: float