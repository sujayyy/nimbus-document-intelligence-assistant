from app.config import settings
from app.generation.llm import LLMClient
from app.generation.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.generation.citation_validator import validate_citations
from app.ingestion.embedder import Embedder
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import FAISSVectorStore


class QueryPipeline:

    def __init__(self):
        self.embedder = Embedder()

        self.retriever = Retriever(
            embedder=self.embedder,
            similarity_threshold=settings.similarity_threshold,
        )

        self.llm = LLMClient()

    def run(
        self,
        document_id: str,
        question: str,
    ):

        # -------------------------
        # 1. Load document index
        # -------------------------

        index_directory = (
            settings.indexes_dir / document_id
        )

        vector_store = FAISSVectorStore(
            index_directory
        )

        vector_store.load()

        # -------------------------
        # 2. Retrieve relevant chunks
        # -------------------------

        results = self.retriever.retrieve(
            vector_store=vector_store,
            question=question,
            top_k=settings.top_k,
        )

        # -------------------------
        # 3. Refuse if retrieval
        #    is too weak
        # -------------------------

        if not results:
            return {
                "document_id": document_id,
                "question": question,
                "answer": (
                    "I don't have enough information "
                    "in the provided document to answer "
                    "that question."
                ),
                "sources": [],
            }

        # -------------------------
        # 4. Extract retrieved chunks
        # -------------------------

        chunks = [
            result.chunk
            for result in results
        ]

        # -------------------------
        # 5. Build grounded prompt
        # -------------------------

        user_prompt = build_user_prompt(
            question=question,
            chunks=chunks,
        )

        # -------------------------
        # 6. Generate answer
        # -------------------------

        answer = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # -------------------------
        # 7. Validate citations
        # -------------------------

        retrieved_pages = {
            result.chunk.page_number
            for result in results
        }

        citation_result = validate_citations(
            answer=answer,
            retrieved_pages=retrieved_pages,
        )

        # -------------------------
        # 8. Refuse if citations
        #    cannot be verified
        # -------------------------

        if not citation_result["valid"]:
            return {
                "document_id": document_id,
                "question": question,
                "answer": (
                    "I couldn't produce a verifiable "
                    "answer from the retrieved "
                    "document evidence."
                ),
                "sources": [],
            }

        # -------------------------
        # 9. Application-controlled
        #    source metadata
        # -------------------------

        sources = []

        for result in results:
            sources.append(
                {
                    "chunk_id": result.chunk.chunk_id,
                    "page_number": result.chunk.page_number,
                    "score": result.score,
                    "text": result.chunk.text,
                }
            )

        # -------------------------
        # 10. Final response
        # -------------------------

        return {
            "document_id": document_id,
            "question": question,
            "answer": answer,
            "sources": sources,
        }