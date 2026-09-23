"""
Controlled chunking experiments.

Motivation (established empirically before running this):

    all-MiniLM-L6-v2 has max_seq_length = 256 tokens, but the
    production chunker emits 512-token chunks. 78% of chunks in
    the production index exceed the embedder's window, and 38.3%
    of all indexed tokens are silently truncated away before the
    embedding is computed.

This harness rebuilds the index from the SAME PDF at different
chunk sizes and re-runs the retrieval variants, so the effect of
chunk size can be measured against a fixed ranking architecture.

Indexes are written to a scratch directory and never touch the
production index.

Usage:

    python -m evaluation.chunking_experiments <document_id> \
        --scratch /path/to/scratch
"""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
EVAL_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(AI_LAYER_DIR))

from app.config import settings  # noqa: E402
from app.ingestion.chunker import TokenChunker  # noqa: E402
from app.ingestion.embedder import Embedder  # noqa: E402
from app.ingestion.parser import PDFParser  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402

from evaluation.experiments.retrieval_experiments import (  # noqa: E402
    ExperimentRetriever,
    Variant,
    score_case,
)


# Chunk configurations under test.
# Overlap is kept at ~10% of chunk size for comparability.
CHUNK_CONFIGS = [
    (256, 25, "256/25  (fits embedder window exactly)"),
    (512, 50, "512/50  (CURRENT PRODUCTION)"),
    (1024, 100, "1024/100 (4x embedder window)"),
    (192, 20, "192/20  (well inside window)"),
]


def build_index(
    pdf_path: Path,
    document_id: str,
    chunk_size: int,
    chunk_overlap: int,
    scratch: Path,
    embedder: Embedder,
) -> FAISSVectorStore:
    """Rebuild an index from the same PDF at a given chunk size."""

    pages = PDFParser().parse(pdf_path)

    chunker = TokenChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = chunker.chunk_pages(
        pages=pages,
        document_id=document_id,
    )

    embeddings = embedder.embed_documents(
        [c.text for c in chunks]
    )

    index_dir = scratch / f"chunk_{chunk_size}_{chunk_overlap}"

    store = FAISSVectorStore(index_dir)
    store.build(embeddings=embeddings, chunks=chunks)

    return store, chunks


def truncation_stats(chunks, embedder) -> dict:
    """How much indexed text the embedder actually sees."""

    tok = embedder.model.tokenizer
    limit = embedder.model.max_seq_length - 2  # special tokens

    lens = [
        len(tok.encode(c.text, add_special_tokens=False))
        for c in chunks
    ]

    total = sum(lens)
    visible = sum(min(l, limit) for l in lens)

    return {
        "chunks": len(chunks),
        "total_tokens": total,
        "visible_tokens": visible,
        "dropped_tokens": total - visible,
        "dropped_pct": (
            100 * (total - visible) / total if total else 0.0
        ),
        "truncated_chunks": sum(1 for l in lens if l > limit),
        "truncated_pct": (
            100 * sum(1 for l in lens if l > limit) / len(lens)
            if lens
            else 0.0
        ),
    }


def run(document_id: str, scratch: Path):
    scratch.mkdir(parents=True, exist_ok=True)

    gold = json.loads(
        (EVAL_DIR / "gold_set.json").read_text(encoding="utf-8")
    )
    answerable = [
        c for c in gold if c.get("type") != "unanswerable"
    ]

    pdf_path = settings.uploads_dir / f"{document_id}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    embedder = Embedder()
    engine = ExperimentRetriever(embedder)

    # Ranking architectures held fixed across chunk sizes.
    fixed_variants = [
        Variant(
            name="dense",
            label="Dense only",
            use_reranker=False,
        ),
        Variant(
            name="ce",
            label="Dense -> CE",
            use_reranker=True,
        ),
        Variant(
            name="prod",
            label="Production (RRF+fin+page)",
            use_reranker=True,
            use_rrf=True,
            use_financial=True,
            use_page_aware=True,
        ),
    ]

    results = {}

    for chunk_size, overlap, label in CHUNK_CONFIGS:
        print(f"\nBuilding index: {label}")

        store, chunks = build_index(
            pdf_path=pdf_path,
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            scratch=scratch,
            embedder=embedder,
        )

        stats = truncation_stats(chunks, embedder)

        print(
            f"   chunks={stats['chunks']} "
            f"truncated={stats['truncated_pct']:.1f}% "
            f"tokens_dropped={stats['dropped_pct']:.1f}%"
        )

        entry = {
            "label": label,
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "truncation": stats,
            "variants": {},
        }

        for variant in fixed_variants:
            per_case = []

            for case in answerable:
                ranked = engine.rank(
                    vector_store=store,
                    question=case["question"],
                    variant=variant,
                )
                m = score_case(
                    case["expected_pages"], ranked
                )
                m["id"] = case["id"]
                per_case.append(m)

            n = len(per_case)
            entry["variants"][variant.name] = {
                "label": variant.label,
                "summary": {
                    "hit_rate": sum(
                        c["hit"] for c in per_case
                    )
                    / n,
                    "recall": sum(
                        c["recall"] for c in per_case
                    )
                    / n,
                    "precision": sum(
                        c["precision"] for c in per_case
                    )
                    / n,
                    "mrr": sum(c["mrr"] for c in per_case)
                    / n,
                    "ndcg": sum(
                        c["ndcg"] for c in per_case
                    )
                    / n,
                },
                "cases": per_case,
            }

        results[f"{chunk_size}_{overlap}"] = entry

    # ---- Table ----
    print("\n" + "=" * 104)
    print("CHUNK SIZE vs RANKING ARCHITECTURE")
    print("=" * 104)
    print(
        f"{'Chunking':<34}{'Trunc%':>8}{'Drop%':>8}"
        f"{'Arch':<28}{'Rec@5':>8}{'MRR':>8}{'nDCG':>8}"
    )
    print("-" * 104)

    for key, e in results.items():
        for i, (vn, v) in enumerate(e["variants"].items()):
            s = v["summary"]
            label = e["label"] if i == 0 else ""
            tp = (
                f"{e['truncation']['truncated_pct']:.0f}%"
                if i == 0
                else ""
            )
            dp = (
                f"{e['truncation']['dropped_pct']:.1f}%"
                if i == 0
                else ""
            )
            print(
                f"{label:<34}{tp:>8}{dp:>8}"
                f"{v['label']:<28}"
                f"{s['recall']:>7.1%}{s['mrr']:>8.3f}"
                f"{s['ndcg']:>8.3f}"
            )
        print("-" * 104)

    out = RESULTS_DIR / "chunking_experiment_results.json"
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
        "--scratch",
        default="/tmp/nimbus_chunking",
        help="Scratch directory for experimental indexes.",
    )
    args = p.parse_args()

    run(args.document_id, Path(args.scratch))


if __name__ == "__main__":
    main()
