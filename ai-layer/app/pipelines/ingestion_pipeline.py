from pathlib import Path

from app.config import settings
from app.ingestion.chunker import TokenChunker
from app.ingestion.embedder import Embedder
from app.ingestion.parser import PDFParser
from app.retrieval.query_preprocessor import detect_subject_entity
from app.retrieval.vector_store import FAISSVectorStore


class IngestionPipeline:

    def __init__(self):

        self.parser = PDFParser()

        self.chunker = TokenChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        self.embedder = Embedder()

    def run(
        self,
        pdf_path: Path,
        document_id: str,
    ):

        print("1. Parsing PDF...")

        pages = self.parser.parse(pdf_path)

        print(
            f"   Extracted text from {len(pages)} pages."
        )

        print("2. Creating chunks...")

        chunks = self.chunker.chunk_pages(
            pages=pages,
            document_id=document_id,
        )

        print(
            f"   Created {len(chunks)} chunks."
        )

        print("3. Generating embeddings...")

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = self.embedder.embed_documents(
            texts
        )

        print(
            f"   Generated embeddings with dimension "
            f"{embeddings.shape[1]}."
        )

        # Terms too common in this document to discriminate between
        # chunks. Stripped from queries before embedding; see
        # query_preprocessor for the measurements behind this.
        subject_entities = detect_subject_entity(pages)

        print(
            f"4. Subject entities: "
            f"{subject_entities or 'none detected'}"
        )

        print("5. Building FAISS index...")

        index_directory = (
            settings.indexes_dir / document_id
        )

        vector_store = FAISSVectorStore(
            index_directory
        )

        vector_store.build(
            embeddings=embeddings,
            chunks=chunks,
            subject_entities=subject_entities,
        )

        print("6. Index saved.")

        return {
            "document_id": document_id,
            "pages": len(pages),
            "chunks": len(chunks),
            "embedding_dimension": embeddings.shape[1],
            "subject_entities": subject_entities,
        }