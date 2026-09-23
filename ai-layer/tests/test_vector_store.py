"""
Tests for the FAISS store, focused on the subject-entity sidecar.

The entities live in their own entities.json rather than as a new key
in metadata.json specifically so that indexes built before detection
existed still load. That promise is what most of these tests check.
"""

import json

import numpy as np
import pytest

from app.retrieval.vector_store import FAISSVectorStore
from app.schemas.documents import DocumentChunk


def make_chunks(count: int = 3) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            chunk_id=f"c{n}",
            document_id="doc",
            page_number=n + 1,
            chunk_index=n,
            text=f"chunk {n} text",
        )
        for n in range(count)
    ]


def make_embeddings(count: int = 3, dimension: int = 8) -> np.ndarray:
    rng = np.random.default_rng(0)

    return rng.random(
        (count, dimension),
        dtype=np.float32,
    )


@pytest.fixture
def store(tmp_path):
    return FAISSVectorStore(tmp_path / "index")


# =====================================================
# Defaults
# =====================================================


def test_fresh_store_has_no_entities(store):
    assert store.subject_entities == []


def test_index_directory_is_created(tmp_path):
    directory = tmp_path / "nested" / "index"

    FAISSVectorStore(directory)

    assert directory.is_dir()


# =====================================================
# Sidecar round trip
# =====================================================


def test_build_writes_the_sidecar(store):
    store.build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
        subject_entities=["acme"],
    )

    assert json.loads(store.entities_path.read_text()) == ["acme"]


def test_entities_survive_a_reload(tmp_path):
    directory = tmp_path / "index"

    FAISSVectorStore(directory).build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
        subject_entities=["acme", "holdings"],
    )

    reopened = FAISSVectorStore(directory)
    reopened.load()

    assert reopened.subject_entities == ["acme", "holdings"]


def test_build_without_entities_writes_an_empty_sidecar(store):
    store.build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
    )

    assert store.subject_entities == []
    assert json.loads(store.entities_path.read_text()) == []


def test_chunks_survive_a_reload(tmp_path):
    directory = tmp_path / "index"
    chunks = make_chunks()

    FAISSVectorStore(directory).build(
        embeddings=make_embeddings(),
        chunks=chunks,
        subject_entities=["acme"],
    )

    reopened = FAISSVectorStore(directory)
    reopened.load()

    assert reopened.chunks == chunks


# =====================================================
# Backward compatibility
# =====================================================


def test_index_predating_the_sidecar_loads_with_no_entities(tmp_path):
    """
    The guarantee that makes this change safe to deploy: an index
    built before subject-entity detection has no entities.json, and
    must load cleanly with an empty list so retrieval behaves exactly
    as it did before.
    """

    directory = tmp_path / "index"

    FAISSVectorStore(directory).build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
        subject_entities=["acme"],
    )

    # Reduce it to a pre-sidecar index on disk.
    (directory / "entities.json").unlink()

    reopened = FAISSVectorStore(directory)
    reopened.load()

    assert reopened.subject_entities == []
    assert len(reopened.chunks) == 3


def test_a_stale_in_memory_entity_list_is_cleared_by_load(tmp_path):
    """
    load() must not leave entities from a previous build in place when
    the index on disk has none, or a reused store would strip terms
    the current index never declared.
    """

    directory = tmp_path / "index"

    store = FAISSVectorStore(directory)
    store.build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
        subject_entities=["acme"],
    )

    (directory / "entities.json").unlink()
    store.load()

    assert store.subject_entities == []


# =====================================================
# Failure modes
# =====================================================


def test_mismatched_lengths_raise(store):
    with pytest.raises(ValueError):
        store.build(
            embeddings=make_embeddings(count=3),
            chunks=make_chunks(count=2),
        )


def test_empty_index_raises(store):
    with pytest.raises(ValueError):
        store.build(
            embeddings=np.zeros((0, 8), dtype=np.float32),
            chunks=[],
        )


def test_load_without_an_index_raises(store):
    with pytest.raises(FileNotFoundError):
        store.load()


def test_load_without_metadata_raises(store):
    store.build(
        embeddings=make_embeddings(),
        chunks=make_chunks(),
    )

    store.metadata_path.unlink()

    with pytest.raises(FileNotFoundError):
        FAISSVectorStore(store.index_directory).load()


def test_save_without_an_index_raises(store):
    with pytest.raises(ValueError):
        store.save()


# =====================================================
# Search
# =====================================================


def test_search_returns_chunks_ranked_with_scores(store):
    embeddings = make_embeddings(count=3)

    store.build(
        embeddings=embeddings,
        chunks=make_chunks(),
    )

    results = store.search(
        query_embedding=embeddings[:1],
        top_k=2,
    )

    assert len(results) == 2
    assert all(
        isinstance(chunk, DocumentChunk) for chunk, _ in results
    )

    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_search_caps_top_k_at_the_index_size(store):
    embeddings = make_embeddings(count=3)

    store.build(
        embeddings=embeddings,
        chunks=make_chunks(),
    )

    results = store.search(
        query_embedding=embeddings[:1],
        top_k=50,
    )

    assert len(results) == 3
