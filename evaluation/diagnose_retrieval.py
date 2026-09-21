import sys
from pathlib import Path


# =========================================================
# Project paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

AI_LAYER_DIR = (
    PROJECT_ROOT / "ai-layer"
)

if str(AI_LAYER_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(AI_LAYER_DIR),
    )


# =========================================================
# AI layer imports
# =========================================================

from app.config import settings
from app.ingestion.embedder import Embedder
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import FAISSVectorStore


# =========================================================
# Configuration
# =========================================================

DOCUMENT_ID = (
    "b7e7f7e4-4fc9-45c1-ab4f-e817b878df3a"
)

INDEX_DIR = (
    Path(settings.indexes_dir)
    / DOCUMENT_ID
)


# =========================================================
# Diagnostic queries
# =========================================================

QUERIES = [
    (
        "R&D",
        "What does the document say about research and development?",
        {17, 27},
    ),
    (
        "Employees",
        "What does the document say about employees?",
        {16},
    ),
    (
        "Competition",
        "What does the document say about competition?",
        {13},
    ),
    (
        "Revenue",
        "What was the company's revenue?",
        {36},
    ),
    (
        "Financial Summary",
        (
            "What were Microsoft's revenue, operating income, "
            "and net income in fiscal year 2025?"
        ),
        {36},
    ),
]


# =========================================================
# Helpers
# =========================================================

def print_separator(
    character="=",
    length=80,
):
    print(
        character * length
    )


# =========================================================
# Main diagnostic
# =========================================================

def main():

    print()

    print(
        "Document Intelligence Assistant"
    )

    print(
        "RRF Retrieval Diagnostic"
    )

    print_separator()

    print(
        f"Document ID: {DOCUMENT_ID}"
    )

    print(
        f"Index directory: {INDEX_DIR}"
    )

    # -----------------------------------------------------
    # Configuration
    # -----------------------------------------------------

    print()

    print(
        "Configuration"
    )

    print("-" * 80)

    print(
        f"Candidate K       : "
        f"{settings.candidate_k}"
    )

    print(
        f"Final Top K       : "
        f"{settings.top_k}"
    )

    print(
        f"Max chunks/page   : "
        f"{settings.max_chunks_per_page}"
    )

    print(
        f"Reranker model    : "
        f"{settings.reranker_model}"
    )

    print(
        "Fusion method     : "
        "Reciprocal Rank Fusion"
    )

    print(
        "Dense contribution: "
        "0.70"
    )

    print(
        "Reranker contribution: "
        "0.30"
    )

    # -----------------------------------------------------
    # Validate index
    # -----------------------------------------------------

    if not INDEX_DIR.exists():

        raise FileNotFoundError(
            "FAISS index directory does not exist: "
            f"{INDEX_DIR}"
        )

    # -----------------------------------------------------
    # Load components
    # -----------------------------------------------------

    print()

    print(
        "Loading embedding model..."
    )

    embedder = Embedder()

    print(
        "Loading FAISS vector store..."
    )

    vector_store = FAISSVectorStore(
        index_directory=INDEX_DIR,
    )

    vector_store.load()

    print(
        "Loading RRF retriever..."
    )

    retriever = Retriever(
        embedder=embedder,
    )

    print(
        "All retrieval components loaded."
    )

    # =====================================================
    # Run diagnostic queries
    # =====================================================

    for (
        name,
        question,
        expected_pages,
    ) in QUERIES:

        print()

        print_separator()

        print(
            f"QUERY: {name}"
        )

        print_separator("-")

        print(
            f"Question: {question}"
        )

        print(
            f"Expected pages: "
            f"{sorted(expected_pages)}"
        )

        # =================================================
        # Production retriever
        # =================================================

        results = retriever.retrieve(
            vector_store=vector_store,
            question=question,
            top_k=settings.top_k,
        )

        print()

        print(
            "FINAL RETRIEVER RESULTS"
        )

        print("-" * 80)

        retrieved_pages = []

        for rank, result in enumerate(
            results,
            start=1,
        ):

            page = (
                result.chunk.page_number
            )

            retrieved_pages.append(
                page
            )

            print(
                f"{rank}. "
                f"RRF score={result.score:.4f} "
                f"page={page} "
                f"chunk={result.chunk.chunk_id}"
            )

            preview = (
                result.chunk.text
                .replace("\n", " ")
                .strip()
            )

            if len(preview) > 220:

                preview = (
                    preview[:220]
                    + "..."
                )

            print(
                f"   {preview}"
            )

        # =================================================
        # Retrieval metrics
        # =================================================

        retrieved_set = set(
            retrieved_pages
        )

        hits = (
            retrieved_set
            & expected_pages
        )

        recall = (
            len(hits)
            / len(expected_pages)
            if expected_pages
            else 0.0
        )

        precision = (
            len(hits)
            / len(retrieved_set)
            if retrieved_set
            else 0.0
        )

        print()

        print(
            f"Retrieved pages       : "
            f"{retrieved_pages}"
        )

        print(
            f"Expected-page recall  : "
            f"{recall:.3f}"
        )

        print(
            f"Page precision        : "
            f"{precision:.3f}"
        )

        # =================================================
        # Detailed ranking analysis
        # =================================================

        print()

        print(
            "RRF RANKING — TOP 20"
        )

        print("-" * 100)

        # -------------------------------------------------
        # Dense FAISS candidates
        # -------------------------------------------------

        query_embedding = (
            retriever.embedder.embed_query(
                question
            )
        )

        candidates = (
            vector_store.search(
                query_embedding=query_embedding,
                top_k=settings.candidate_k,
            )
        )

        if not candidates:

            print(
                "No FAISS candidates found."
            )

            continue

        # -------------------------------------------------
        # Dense ranking
        # -------------------------------------------------

        dense_records = []

        for dense_rank, (
            chunk,
            dense_score,
        ) in enumerate(
            candidates,
            start=1,
        ):

            dense_records.append(
                {
                    "chunk": chunk,
                    "dense_score": float(
                        dense_score
                    ),
                    "dense_rank": dense_rank,
                }
            )

        # -------------------------------------------------
        # Cross-encoder scores
        # -------------------------------------------------

        pairs = [
            (
                question,
                record["chunk"].text,
            )
            for record in dense_records
        ]

        reranker_scores = (
            retriever.reranker.predict(
                pairs
            )
        )

        reranker_scores = [
            float(score)
            for score in reranker_scores
        ]

        # -------------------------------------------------
        # Add reranker scores
        # -------------------------------------------------

        for index, record in enumerate(
            dense_records
        ):

            record["reranker_score"] = (
                reranker_scores[index]
            )

        # -------------------------------------------------
        # Reranker ranking
        # -------------------------------------------------

        reranked_records = sorted(
            dense_records,
            key=lambda record: (
                record["reranker_score"]
            ),
            reverse=True,
        )

        for reranker_rank, record in enumerate(
            reranked_records,
            start=1,
        ):

            record["reranker_rank"] = (
                reranker_rank
            )

        # -------------------------------------------------
        # RRF score
        # -------------------------------------------------

        for record in dense_records:

            record["rrf_score"] = (
                retriever._rrf_score(
                    dense_rank=(
                        record["dense_rank"]
                    ),
                    reranker_rank=(
                        record["reranker_rank"]
                    ),
                )
            )

        # -------------------------------------------------
        # Final RRF ranking
        # -------------------------------------------------

        rrf_records = sorted(
            dense_records,
            key=lambda record: (
                record["rrf_score"]
            ),
            reverse=True,
        )

        # -------------------------------------------------
        # Print ranking table
        # -------------------------------------------------

        print(
            f"{'':1}"
            f"{'RRF':>4} "
            f"{'FAISS':>6} "
            f"{'RERANK':>7} "
            f"{'PAGE':>6} "
            f"{'DENSE':>9} "
            f"{'CE':>9} "
            f"{'RRF SCORE':>10}"
        )

        print("-" * 100)

        for rrf_rank, record in enumerate(
            rrf_records[:20],
            start=1,
        ):

            page = (
                record["chunk"].page_number
            )

            marker = (
                "*"
                if page in expected_pages
                else " "
            )

            print(
                f"{marker}"
                f"{rrf_rank:>4} "
                f"{record['dense_rank']:>6} "
                f"{record['reranker_rank']:>7} "
                f"{page:>6} "
                f"{record['dense_score']:>9.4f} "
                f"{record['reranker_score']:>9.4f} "
                f"{record['rrf_score']:>10.4f}"
            )

        print()

        print(
            "* = expected page"
        )

        # =================================================
        # Expected page positions
        # =================================================

        print()

        print(
            "EXPECTED PAGE POSITIONS"
        )

        print("-" * 100)

        for expected_page in sorted(
            expected_pages
        ):

            matches = [
                (
                    rank,
                    record,
                )
                for rank, record in enumerate(
                    rrf_records,
                    start=1,
                )
                if record["chunk"].page_number
                == expected_page
            ]

            if not matches:

                print(
                    f"Page {expected_page}: "
                    f"NOT FOUND in FAISS top "
                    f"{settings.candidate_k}"
                )

                continue

            rrf_rank, record = matches[0]

            print(
                f"Page {expected_page}: "
                f"RRF rank={rrf_rank}, "
                f"FAISS rank="
                f"{record['dense_rank']}, "
                f"reranker rank="
                f"{record['reranker_rank']}, "
                f"dense="
                f"{record['dense_score']:.4f}, "
                f"reranker="
                f"{record['reranker_score']:.4f}, "
                f"RRF="
                f"{record['rrf_score']:.4f}"
            )

    # =====================================================
    # Completion
    # =====================================================

    print()

    print_separator()

    print(
        "RRF retrieval diagnostic completed."
    )

    print_separator()


# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":
    main()