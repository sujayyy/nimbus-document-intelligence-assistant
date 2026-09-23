"""
Tests for the retrieval pipeline's wiring.

Retriever.__init__ downloads and loads a CrossEncoder, so these tests
build the object with __new__ and inject fakes. That keeps the suite
fast and offline while still exercising the real retrieve() path.
"""

import numpy as np
import pytest

from app.retrieval.retriever import Retriever
from app.schemas.documents import DocumentChunk


class FakeEmbedder:
    """Records every query it is asked to embed."""

    def __init__(self):
        self.embedded: list[str] = []

    def embed_query(self, text: str) -> np.ndarray:
        self.embedded.append(text)

        return np.zeros((1, 8), dtype=np.float32)


class FakeVectorStore:

    def __init__(self, chunks, subject_entities=None):
        self.chunks = chunks

        if subject_entities is not None:
            self.subject_entities = subject_entities

    def search(self, query_embedding, top_k):
        return [
            (chunk, 1.0 - index * 0.01)
            for index, chunk in enumerate(self.chunks[:top_k])
        ]


class FakeReranker:
    """Records the (question, chunk) pairs it is asked to score."""

    def __init__(self):
        self.pairs: list[tuple[str, str]] = []

    def predict(self, pairs):
        self.pairs = list(pairs)

        return [1.0 for _ in pairs]


def make_chunks(count: int = 4) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            chunk_id=f"c{n}",
            document_id="doc",
            page_number=n + 1,
            chunk_index=n,
            text=f"Total revenue for Acme in 2023 was {n}00.",
        )
        for n in range(count)
    ]


@pytest.fixture
def retriever():
    instance = Retriever.__new__(Retriever)

    instance.embedder = FakeEmbedder()
    instance.reranker = FakeReranker()
    instance.similarity_threshold = 0.0

    return instance


# =====================================================
# Subject-entity stripping
# =====================================================


def test_dense_query_is_stripped(retriever):
    store = FakeVectorStore(make_chunks(), subject_entities=["acme"])

    retriever.retrieve(
        vector_store=store,
        question="What was Acme total revenue?",
        top_k=2,
    )

    assert retriever.embedder.embedded == [
        "What was total revenue?"
    ]


def test_reranker_still_receives_the_original_question(retriever):
    """
    The asymmetry that makes the fix work. The CrossEncoder reads
    question and chunk together and is far less sensitive to the
    subject entity, so it must keep the full question even though
    the embedder does not.
    """

    store = FakeVectorStore(make_chunks(), subject_entities=["acme"])

    question = "What was Acme total revenue?"

    retriever.retrieve(
        vector_store=store,
        question=question,
        top_k=2,
    )

    assert retriever.reranker.pairs
    assert all(pair[0] == question for pair in retriever.reranker.pairs)


def test_store_without_entities_embeds_the_question_unchanged(retriever):
    store = FakeVectorStore(make_chunks(), subject_entities=[])

    retriever.retrieve(
        vector_store=store,
        question="What was Acme total revenue?",
        top_k=2,
    )

    assert retriever.embedder.embedded == [
        "What was Acme total revenue?"
    ]


def test_store_predating_the_attribute_does_not_crash(retriever):
    """
    _retrieve_candidates reads subject_entities with getattr and a
    None default, so a store object from before the change still
    retrieves rather than raising AttributeError.
    """

    store = FakeVectorStore(make_chunks())

    assert not hasattr(store, "subject_entities")

    results = retriever.retrieve(
        vector_store=store,
        question="What was Acme total revenue?",
        top_k=2,
    )

    assert results
    assert retriever.embedder.embedded == [
        "What was Acme total revenue?"
    ]


# =====================================================
# Guards
# =====================================================


def test_blank_question_returns_nothing(retriever):
    store = FakeVectorStore(make_chunks(), subject_entities=["acme"])

    assert retriever.retrieve(store, "   ", top_k=2) == []
    assert retriever.embedder.embedded == []


def test_empty_candidate_pool_returns_nothing(retriever):
    store = FakeVectorStore([], subject_entities=["acme"])

    assert retriever.retrieve(store, "revenue?", top_k=2) == []


def test_results_are_capped_at_top_k(retriever):
    store = FakeVectorStore(make_chunks(count=8), subject_entities=[])

    results = retriever.retrieve(store, "revenue?", top_k=3)

    assert len(results) == 3


# =====================================================
# Financial signal
# =====================================================


def test_financial_queries_are_detected(retriever):
    assert retriever._is_financial_query("What was total revenue?")
    assert retriever._is_financial_query("Show the balance sheet")
    assert not retriever._is_financial_query("Who is the chairman?")


def test_non_financial_query_scores_zero(retriever):
    assert (
        retriever._financial_score(
            question="Who is the chairman?",
            text="Total revenue for the year ended 2023.",
        )
        == 0.0
    )


def test_financial_score_rewards_matching_metrics_and_years(retriever):
    matching = retriever._financial_score(
        question="What was total revenue in 2023?",
        text="Total revenue for the year ended 2023 was 100.",
    )

    unrelated = retriever._financial_score(
        question="What was total revenue in 2023?",
        text="The chairman addressed the shareholders.",
    )

    assert matching > unrelated
    assert 0.0 <= matching <= 1.0


def test_normalisation_folds_case_and_separators(retriever):
    assert (
        retriever._normalize_text("Total-Revenue (Net), 2023:")
        == "total revenue  net   2023 "
    )


# =====================================================
# Rank fusion and page-aware selection
# =====================================================


def test_better_ranks_score_higher(retriever):
    assert Retriever._rrf_score(1, 1) > Retriever._rrf_score(5, 5)


def test_page_aware_selection_limits_chunks_per_page(retriever):
    """
    Six candidates all on page 1. The per-page cap applies first, then
    the fallback tops the selection back up to top_k so the caller
    always gets what it asked for when candidates exist.
    """

    candidates = [
        {
            "chunk": DocumentChunk(
                chunk_id=f"c{n}",
                document_id="doc",
                page_number=1,
                chunk_index=n,
                text="text",
            )
        }
        for n in range(6)
    ]

    selected = Retriever._select_page_aware(candidates, top_k=4)

    assert len(selected) == 4

    ids = [item["chunk"].chunk_id for item in selected]
    assert len(set(ids)) == 4
