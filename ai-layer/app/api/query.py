import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import settings
from app.generation.llm import LLMClient
from app.generation.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.generation.citation_validator import validate_citations
from app.pipelines.query_pipeline import QueryPipeline
from app.retrieval.vector_store import FAISSVectorStore


router = APIRouter()

query_pipeline = QueryPipeline()
llm_client = LLMClient()


# ============================================================
# Normal Query
# ============================================================

@router.post("/query")
def query_document(
    document_id: str,
    question: str,
):
    return query_pipeline.run(
        document_id,
        question,
    )


# ============================================================
# Streaming Query
# ============================================================

@router.post("/query/stream")
def stream_query(
    document_id: str,
    question: str,
):

    # --------------------------------------------------------
    # 1. Load document-specific vector store
    # --------------------------------------------------------

    vector_store = FAISSVectorStore(
        settings.indexes_dir / document_id
    )

    vector_store.load()

    # --------------------------------------------------------
    # 2. Retrieve relevant chunks
    # --------------------------------------------------------

    retrieved = query_pipeline.retriever.retrieve(
        vector_store=vector_store,
        question=question,
        top_k=settings.top_k,
    )

    # --------------------------------------------------------
    # Helper for SSE events
    # --------------------------------------------------------

    def event(
        event_type: str,
        data,
    ) -> str:

        return (
            f"event: {event_type}\n"
            f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        )

    # --------------------------------------------------------
    # 3. Refuse if retrieval is too weak
    # --------------------------------------------------------

    if not retrieved:

        def refusal():

            yield event(
                "token",
                "I don't have enough information in the provided "
                "document to answer that question.",
            )

            yield event(
                "citation_validation",
                {
                    "valid": False,
                    "cited_pages": [],
                    "invalid_pages": [],
                },
            )

            yield event(
                "sources",
                [],
            )

            yield event(
                "done",
                {},
            )

        return StreamingResponse(
            refusal(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # --------------------------------------------------------
    # 4. Extract chunks
    # --------------------------------------------------------

    chunks = [
        result.chunk
        for result in retrieved
    ]

    # --------------------------------------------------------
    # 5. Build grounded prompt
    # --------------------------------------------------------

    user_prompt = build_user_prompt(
        question=question,
        chunks=chunks,
    )

    # --------------------------------------------------------
    # 6. Stream Claude response
    # --------------------------------------------------------

    def generate():

        answer_parts = []

        for text in llm_client.generate_stream(
            SYSTEM_PROMPT,
            user_prompt,
        ):

            answer_parts.append(text)

            yield event(
                "token",
                text,
            )

        # ----------------------------------------------------
        # 7. Reconstruct complete answer
        # ----------------------------------------------------

        answer = "".join(answer_parts)

        # ----------------------------------------------------
        # 8. Validate citations
        # ----------------------------------------------------

        retrieved_pages = {
            result.chunk.page_number
            for result in retrieved
        }

        citation_result = validate_citations(
            answer=answer,
            retrieved_pages=retrieved_pages,
        )

        # ----------------------------------------------------
        # 9. Send citation validation result
        # ----------------------------------------------------

        yield event(
            "citation_validation",
            citation_result,
        )

        # ----------------------------------------------------
        # 10. Application-controlled sources
        # ----------------------------------------------------

        sources = []

        for result in retrieved:

            sources.append(
                {
                    "chunk_id": result.chunk.chunk_id,
                    "page_number": result.chunk.page_number,
                    "score": result.score,
                    "text": result.chunk.text,
                }
            )

        # ----------------------------------------------------
        # 11. Send sources only if citations are valid
        # ----------------------------------------------------

        if citation_result["valid"]:

            yield event(
                "sources",
                sources,
            )

        else:

            yield event(
                "sources",
                [],
            )

        # ----------------------------------------------------
        # 12. Signal completion
        # ----------------------------------------------------

        yield event(
            "done",
            {},
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )