import json
from pathlib import Path

import faiss
import numpy as np

from app.schemas.documents import DocumentChunk


class FAISSVectorStore:

    def __init__(self, index_directory: Path):
        self.index_directory = index_directory
        self.index_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index_path = self.index_directory / "index.faiss"
        self.metadata_path = self.index_directory / "metadata.json"

        # Sidecar rather than a new key in metadata.json, so indexes
        # built before subject-entity detection still load unchanged.
        self.entities_path = (
            self.index_directory / "entities.json"
        )

        self.index = None
        self.chunks: list[DocumentChunk] = []

        # Terms so common in this document that they cannot
        # discriminate between chunks. Empty for older indexes.
        self.subject_entities: list[str] = []

    def build(
        self,
        embeddings: np.ndarray,
        chunks: list[DocumentChunk],
        subject_entities: list[str] | None = None,
    ) -> None:

        self.subject_entities = list(
            subject_entities or []
        )

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Number of embeddings must match number of chunks."
            )

        if len(embeddings) == 0:
            raise ValueError("Cannot build an empty vector index.")

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dimension)

        self.index.add(embeddings)

        self.chunks = chunks

        self.save()

    def save(self) -> None:

        if self.index is None:
            raise ValueError("No FAISS index exists.")

        faiss.write_index(
            self.index,
            str(self.index_path),
        )

        metadata = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
            }
            for chunk in self.chunks
        ]

        with self.metadata_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2,
            )

        with self.entities_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                self.subject_entities,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def load(self) -> None:

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {self.index_path}"
            )

        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata not found: {self.metadata_path}"
            )

        self.index = faiss.read_index(
            str(self.index_path)
        )

        with self.metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            metadata = json.load(file)

        self.chunks = [
            DocumentChunk(**item)
            for item in metadata
        ]

        # Absent for indexes built before subject-entity detection;
        # retrieval then behaves exactly as it did before.
        if self.entities_path.exists():

            with self.entities_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                self.subject_entities = json.load(file)

        else:
            self.subject_entities = []

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
    ) -> list[tuple[DocumentChunk, float]]:

        if self.index is None:
            self.load()

        if self.index.ntotal == 0:
            return []

        actual_k = min(
            top_k,
            self.index.ntotal,
        )

        scores, indices = self.index.search(
            query_embedding,
            actual_k,
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):

            if index < 0:
                continue

            results.append(
                (
                    self.chunks[index],
                    float(score),
                )
            )

        return results