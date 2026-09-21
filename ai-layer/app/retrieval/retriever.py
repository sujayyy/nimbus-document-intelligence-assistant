from sentence_transformers import CrossEncoder

from app.config import settings
from app.ingestion.embedder import Embedder
from app.retrieval.vector_store import FAISSVectorStore
from app.schemas.documents import RetrievedChunk


class Retriever:
    """
    Query-aware rank-fusion document retriever.

    Retrieval pipeline:

        Question
            ↓
        Dense FAISS retrieval
            ↓
        Broad candidate pool
            ↓
        Cross-encoder reranking
            ↓
        Reciprocal Rank Fusion
            ↓
        Query-aware financial matching
            ↓
        Page-aware selection
            ↓
        Final top-k chunks

    Dense retrieval provides semantic recall.

    CrossEncoder provides deeper query/chunk relevance.

    Reciprocal Rank Fusion combines the two rankings without
    directly comparing their incompatible raw score scales.

    Query-aware financial matching provides a small additional
    signal for structured financial questions that request
    multiple financial metrics.
    """

    # =====================================================
    # Financial terms
    # =====================================================

    FINANCIAL_TERMS = {
        "revenue",
        "total revenue",
        "operating income",
        "net income",
        "gross margin",
        "income before income taxes",
        "income taxes",
        "research and development",
        "sales and marketing",
        "earnings per share",
        "cash and cash equivalents",
        "total assets",
        "total liabilities",
    }

    FINANCIAL_STATEMENT_TERMS = {
        "income statements",
        "income statement",
        "financial statements",
        "balance sheets",
        "balance sheet",
        "year ended",
        "fiscal year",
    }

    YEAR_TERMS = {
        "2025",
        "2024",
        "2023",
    }

    def __init__(
        self,
        embedder: Embedder,
        similarity_threshold: float = (
            settings.similarity_threshold
        ),
    ):
        self.embedder = embedder

        self.similarity_threshold = (
            similarity_threshold
        )

        self.reranker = CrossEncoder(
            settings.reranker_model
        )

    # =====================================================
    # Candidate retrieval
    # =====================================================

    def _retrieve_candidates(
        self,
        vector_store: FAISSVectorStore,
        question: str,
    ):
        """
        Retrieve a broad semantic candidate pool using FAISS.
        """

        query_embedding = (
            self.embedder.embed_query(
                question
            )
        )

        return vector_store.search(
            query_embedding=query_embedding,
            top_k=settings.candidate_k,
        )

    # =====================================================
    # Token normalization
    # =====================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        return (
            text.lower()
            .replace("-", " ")
            .replace("/", " ")
            .replace(",", " ")
            .replace(":", " ")
            .replace("(", " ")
            .replace(")", " ")
        )

    # =====================================================
    # Financial query detection
    # =====================================================

    def _is_financial_query(
        self,
        question: str,
    ) -> bool:
        """
        Determine whether the query appears to be asking
        about structured financial information.
        """

        normalized = self._normalize_text(
            question
        )

        for term in self.FINANCIAL_TERMS:

            if term in normalized:
                return True

        for term in self.FINANCIAL_STATEMENT_TERMS:

            if term in normalized:
                return True

        return False

    # =====================================================
    # Financial query-aware score
    # =====================================================

    def _financial_score(
        self,
        question: str,
        text: str,
    ) -> float:
        """
        Calculate a small query-aware signal for financial
        questions.

        The score rewards chunks containing:

        1. Requested financial metrics
        2. Financial-statement terminology
        3. Requested years

        This score is intentionally used as a small adjustment
        after RRF rather than replacing semantic retrieval.
        """

        if not self._is_financial_query(
            question
        ):
            return 0.0

        question_normalized = (
            self._normalize_text(
                question
            )
        )

        text_normalized = (
            self._normalize_text(
                text
            )
        )

        score = 0.0

        # -------------------------------------------------
        # Financial metric matches
        # -------------------------------------------------

        matched_metrics = 0

        for term in self.FINANCIAL_TERMS:

            if (
                term in question_normalized
                and term in text_normalized
            ):
                matched_metrics += 1

        if matched_metrics > 0:

            score += min(
                matched_metrics / 3.0,
                1.0,
            ) * 0.70

        # -------------------------------------------------
        # Financial statement context
        # -------------------------------------------------

        statement_matches = 0

        for term in (
            self.FINANCIAL_STATEMENT_TERMS
        ):

            if term in text_normalized:
                statement_matches += 1

        if statement_matches > 0:

            score += 0.20

        # -------------------------------------------------
        # Requested year matches
        # -------------------------------------------------

        year_matches = 0

        for year in self.YEAR_TERMS:

            if (
                year in question_normalized
                and year in text_normalized
            ):
                year_matches += 1

        if year_matches > 0:

            score += min(
                year_matches / 2.0,
                1.0,
            ) * 0.10

        return min(
            score,
            1.0,
        )

    # =====================================================
    # Reciprocal Rank Fusion
    # =====================================================

    @staticmethod
    def _rrf_score(
        dense_rank: int,
        reranker_rank: int,
        dense_weight: float = (
            settings.rrf_dense_weight
        ),
        reranker_weight: float = (
            settings.rrf_reranker_weight
        ),
        k: int = settings.rrf_k,
    ) -> float:
        """
        Combine dense and CrossEncoder rankings using RRF.
        """

        dense_component = (
            dense_weight
            / (k + dense_rank)
        )

        reranker_component = (
            reranker_weight
            / (k + reranker_rank)
        )

        return (
            dense_component
            + reranker_component
        )

    # =====================================================
    # Page-aware selection
    # =====================================================

    @staticmethod
    def _select_page_aware(
        scored_candidates,
        top_k: int,
    ):
        """
        Select final chunks while limiting the number of
        chunks contributed by the same page.
        """

        selected = []

        page_counts: dict[int, int] = {}

        max_chunks_per_page = (
            settings.max_chunks_per_page
        )

        for candidate in scored_candidates:

            page_number = (
                candidate["chunk"].page_number
            )

            current_count = (
                page_counts.get(
                    page_number,
                    0,
                )
            )

            if (
                current_count
                >= max_chunks_per_page
            ):
                continue

            selected.append(
                candidate
            )

            page_counts[page_number] = (
                current_count + 1
            )

            if len(selected) >= top_k:
                break

        # -------------------------------------------------
        # Fallback
        # -------------------------------------------------

        if len(selected) < top_k:

            selected_ids = {
                candidate["chunk"].chunk_id
                for candidate in selected
            }

            for candidate in scored_candidates:

                chunk_id = (
                    candidate["chunk"].chunk_id
                )

                if chunk_id in selected_ids:
                    continue

                selected.append(
                    candidate
                )

                if len(selected) >= top_k:
                    break

        return selected

    # =====================================================
    # Main retrieval
    # =====================================================

    def retrieve(
        self,
        vector_store: FAISSVectorStore,
        question: str,
        top_k: int = settings.top_k,
    ) -> list[RetrievedChunk]:

        question = question.strip()

        if not question:
            return []

        # -------------------------------------------------
        # Stage 1: Dense FAISS retrieval
        # -------------------------------------------------

        candidate_results = (
            self._retrieve_candidates(
                vector_store=vector_store,
                question=question,
            )
        )

        if not candidate_results:
            return []

        # -------------------------------------------------
        # Stage 2: Store dense ranking
        # -------------------------------------------------

        candidates = []

        for dense_rank, (
            chunk,
            dense_score,
        ) in enumerate(
            candidate_results,
            start=1,
        ):

            candidates.append(
                {
                    "chunk": chunk,
                    "dense_score": float(
                        dense_score
                    ),
                    "dense_rank": dense_rank,
                }
            )

        # -------------------------------------------------
        # Stage 3: CrossEncoder reranking
        # -------------------------------------------------

        pairs = [
            (
                question,
                candidate["chunk"].text,
            )
            for candidate in candidates
        ]

        reranker_scores = (
            self.reranker.predict(
                pairs
            )
        )

        reranker_scores = [
            float(score)
            for score in reranker_scores
        ]

        for index, candidate in enumerate(
            candidates
        ):

            candidate["reranker_score"] = (
                reranker_scores[index]
            )

        # -------------------------------------------------
        # Stage 4: Reranker ranking
        # -------------------------------------------------

        reranked_candidates = sorted(
            candidates,
            key=lambda item: (
                item["reranker_score"]
            ),
            reverse=True,
        )

        for reranker_rank, candidate in enumerate(
            reranked_candidates,
            start=1,
        ):

            candidate["reranker_rank"] = (
                reranker_rank
            )

        # -------------------------------------------------
        # Stage 5: RRF
        # -------------------------------------------------

        for candidate in candidates:

            candidate["rrf_score"] = (
                self._rrf_score(
                    dense_rank=(
                        candidate["dense_rank"]
                    ),
                    reranker_rank=(
                        candidate["reranker_rank"]
                    ),
                )
            )

        # -------------------------------------------------
        # Stage 6: Query-aware financial signal
        # -------------------------------------------------

        for candidate in candidates:

            candidate["financial_score"] = (
                self._financial_score(
                    question=question,
                    text=candidate[
                        "chunk"
                    ].text,
                )
            )

            candidate["final_score"] = (
                candidate["rrf_score"]
                + (
                    settings.financial_query_weight
                    * candidate[
                        "financial_score"
                    ]
                )
            )

        # -------------------------------------------------
        # Stage 7: Final ranking
        # -------------------------------------------------

        candidates.sort(
            key=lambda item: (
                item["final_score"]
            ),
            reverse=True,
        )

        # -------------------------------------------------
        # Stage 8: Page-aware selection
        # -------------------------------------------------

        selected = self._select_page_aware(
            scored_candidates=candidates,
            top_k=top_k,
        )

        # -------------------------------------------------
        # Stage 9: Convert to RetrievedChunk
        # -------------------------------------------------

        results = []

        for candidate in selected:

            results.append(
                RetrievedChunk(
                    chunk=candidate["chunk"],
                    score=float(
                        candidate["final_score"]
                    ),
                )
            )

        return results