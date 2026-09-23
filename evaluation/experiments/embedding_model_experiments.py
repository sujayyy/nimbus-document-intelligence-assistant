"""
Does moving to a 512-token embedding model fix the truncation defect?

Established earlier: all-MiniLM-L6-v2 has a 256-token window while the
chunker emits 512-token chunks, so 38.3% of indexed tokens never reach
the embedding. v2.1 case 5 (diluted EPS) is a live victim - the figure
sits in the discarded tail of the page-36 chunk.

Two effects are confounded in a naive model swap:

    1. truncation removal (512-token window vs 256)
    2. model quality      (BGE / E5 are stronger than MiniLM generally)

So the matrix includes MiniLM at a chunk size that fits its own window,
which isolates (1) within a single model.

The CrossEncoder is held constant throughout, so only the dense stage
varies.

Usage:
    python -m evaluation.embedding_model_experiments <document_id>
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
EVAL_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(AI_LAYER_DIR))

from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import settings  # noqa: E402
from app.ingestion.chunker import TokenChunker  # noqa: E402
from app.ingestion.parser import PDFParser  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402

from evaluation.experiments.retrieval_experiments import (  # noqa: E402
    ExperimentRetriever,
    Variant,
    load_gold,
    score_case,
)


# =========================================================
# Model specs
# =========================================================


@dataclass
class ModelSpec:
    """
    An embedding model plus the prompt conventions it was trained
    with. Using the wrong convention materially degrades retrieval,
    so these are not optional decoration:

      - BGE v1.5 expects an instruction on the QUERY only for
        short-query / long-passage retrieval.
      - E5 requires "query: " and "passage: " on both sides.
      - MiniLM uses neither.
    """

    key: str
    name: str
    label: str
    chunk_size: int
    chunk_overlap: int
    query_prefix: str = ""
    passage_prefix: str = ""


BGE_Q = "Represent this sentence for searching relevant passages: "

MODEL_SPECS = [
    ModelSpec(
        key="minilm_512",
        name="sentence-transformers/all-MiniLM-L6-v2",
        label="MiniLM-L6 @ 512 chunks (CURRENT)",
        chunk_size=512,
        chunk_overlap=50,
    ),
    ModelSpec(
        key="minilm_254",
        name="sentence-transformers/all-MiniLM-L6-v2",
        label="MiniLM-L6 @ 254 chunks (no truncation)",
        chunk_size=254,
        chunk_overlap=25,
    ),
    ModelSpec(
        key="bge_base_512",
        name="BAAI/bge-base-en-v1.5",
        label="BGE-base-v1.5 @ 512 chunks",
        chunk_size=512,
        chunk_overlap=50,
        query_prefix=BGE_Q,
    ),
    ModelSpec(
        key="bge_small_512",
        name="BAAI/bge-small-en-v1.5",
        label="BGE-small-v1.5 @ 512 chunks",
        chunk_size=512,
        chunk_overlap=50,
        query_prefix=BGE_Q,
    ),
    ModelSpec(
        key="e5_base_512",
        name="intfloat/e5-base-v2",
        label="E5-base-v2 @ 512 chunks",
        chunk_size=512,
        chunk_overlap=50,
        query_prefix="query: ",
        passage_prefix="passage: ",
    ),
]


# =========================================================
# Embedder honouring each model's prompt convention
# =========================================================


class SpecEmbedder:
    """Mirrors app.ingestion.Embedder but applies prefixes."""

    def __init__(self, spec: ModelSpec):
        self.spec = spec
        self.model = SentenceTransformer(spec.name)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if self.spec.passage_prefix:
            texts = [
                self.spec.passage_prefix + t for t in texts
            ]

        emb = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return emb.astype("float32")

    def embed_query(self, text: str) -> np.ndarray:
        emb = self.model.encode(
            [self.spec.query_prefix + text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return emb.astype("float32")


def truncation_stats(chunks, model) -> dict:
    tok = model.tokenizer
    limit = model.max_seq_length - 2

    lens = [
        len(tok.encode(c.text, add_special_tokens=False))
        for c in chunks
    ]
    total = sum(lens)
    visible = sum(min(l, limit) for l in lens)

    return {
        "window": model.max_seq_length,
        "chunks": len(chunks),
        "mean_tokens": total / len(lens),
        "truncated_pct": 100
        * sum(1 for l in lens if l > limit)
        / len(lens),
        "dropped_pct": 100 * (total - visible) / total,
    }


# =========================================================
# Runner
# =========================================================

VARIANTS = [
    ("dense", Variant("d", "Dense only", use_reranker=False)),
    ("ce", Variant("c", "Dense->CE", use_reranker=True)),
    (
        "rrf",
        Variant("r", "Dense+CE->RRF", use_reranker=True, use_rrf=True),
    ),
    (
        "prod",
        Variant(
            "p",
            "Production",
            use_reranker=True,
            use_rrf=True,
            use_financial=True,
            use_page_aware=True,
        ),
    ),
]

# v2.1 case 5 is the diluted-EPS probe: the figure lives in the
# truncated tail of the page-36 chunk.
EPS_CASE_ID = 5


def evaluate(engine, store, cases, variant) -> dict:
    per = []
    for case in cases:
        ranked = engine.rank(store, case["question"], variant)
        m = score_case(
            case["primary"], ranked, case["acceptable"]
        )
        m["id"] = case["id"]
        per.append(m)

    n = len(per)
    return {
        "recall": sum(c["recall"] for c in per) / n,
        "adjusted_precision": sum(
            c["adjusted_precision"] for c in per
        )
        / n,
        "mrr": sum(c["mrr"] for c in per) / n,
        "ndcg_graded": sum(
            c["ndcg_graded"] for c in per
        )
        / n,
        "cases": per,
    }


def run(document_id: str, scratch: Path):
    scratch.mkdir(parents=True, exist_ok=True)

    gold = [
        c
        for c in load_gold(EVAL_DIR / "gold_set.json")
        if c["type"] != "unanswerable"
    ]

    pdf_path = settings.uploads_dir / f"{document_id}.pdf"
    pages = PDFParser().parse(pdf_path)

    results = {}

    for spec in MODEL_SPECS:
        print(f"\n=== {spec.label} ===")

        embedder = SpecEmbedder(spec)

        chunker = TokenChunker(
            model_name=spec.name,
            chunk_size=spec.chunk_size,
            chunk_overlap=spec.chunk_overlap,
        )
        chunks = chunker.chunk_pages(pages, document_id)

        stats = truncation_stats(chunks, embedder.model)
        print(
            f"  window={stats['window']} chunks={stats['chunks']} "
            f"mean_tok={stats['mean_tokens']:.0f} "
            f"truncated={stats['truncated_pct']:.1f}% "
            f"dropped={stats['dropped_pct']:.1f}%"
        )

        emb = embedder.embed_documents(
            [c.text for c in chunks]
        )

        store = FAISSVectorStore(scratch / spec.key)
        store.build(embeddings=emb, chunks=chunks)

        engine = ExperimentRetriever(embedder)

        entry = {
            "label": spec.label,
            "model": spec.name,
            "chunk_size": spec.chunk_size,
            "query_prefix": spec.query_prefix,
            "truncation": stats,
            "v1": {},
            "v2": {},
        }

        for vname, variant in VARIANTS:
            entry["v1"][vname] = evaluate(
                engine, store, gold, variant
            )
            entry["v2"][vname] = evaluate(
                engine, store, gold, variant
            )

        # EPS probe under dense only - the truncation smoking gun.
        eps = next(
            (
                c
                for c in entry["v2"]["dense"]["cases"]
                if c["id"] == EPS_CASE_ID
            ),
            None,
        )
        entry["eps_dense_recall"] = (
            eps["recall"] if eps else None
        )

        results[spec.key] = entry

    # ---------------- tables ----------------
    for gold_key, gold_label, n in [
        ("v2", "GOLD v2.1 (corrected)", len(gold)),
        ("v1", "GOLD v1 (original)", len(gold)),
    ]:
        print("\n" + "=" * 104)
        print(
            f"EMBEDDING MODEL COMPARISON - {gold_label}, "
            f"{n} cases, top_k=5"
        )
        print("=" * 104)
        print(
            f"{'Embedding config':<38}{'drop%':>7}  "
            f"{'Arch':<15}{'Rec@5':>8}{'AdjP@5':>8}"
            f"{'MRR':>8}{'nDCGg':>8}"
        )
        print("-" * 104)

        for key, e in results.items():
            for i, (vname, _) in enumerate(VARIANTS):
                s = e[gold_key][vname]
                lbl = e["label"] if i == 0 else ""
                dp = (
                    f"{e['truncation']['dropped_pct']:.1f}"
                    if i == 0
                    else ""
                )
                arch = dict(
                    dense="Dense",
                    ce="Dense->CE",
                    rrf="RRF",
                    prod="Production",
                )[vname]
                print(
                    f"{lbl:<38}{dp:>7}  {arch:<15}"
                    f"{s['recall']:>7.1%}"
                    f"{s['adjusted_precision']:>8.1%}"
                    f"{s['mrr']:>8.3f}"
                    f"{s['ndcg_graded']:>8.3f}"
                )
            print("-" * 104)

    print("\n" + "=" * 70)
    print("TRUNCATION PROBE - v2.1 case 5 (diluted EPS), dense only")
    print("EPS sits in the discarded tail of the page-36 chunk.")
    print("=" * 70)
    for key, e in results.items():
        r = e["eps_dense_recall"]
        mark = "FOUND" if r and r > 0 else "MISSED"
        print(
            f"  {e['label']:<42} window={e['truncation']['window']:<5} {mark}"
        )
    print("=" * 70)

    out = RESULTS_DIR / "embedding_model_results.json"
    out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")

    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("document_id")
    p.add_argument(
        "--scratch", default="/tmp/nimbus_embedding"
    )
    a = p.parse_args()
    run(a.document_id, Path(a.scratch))


if __name__ == "__main__":
    main()
