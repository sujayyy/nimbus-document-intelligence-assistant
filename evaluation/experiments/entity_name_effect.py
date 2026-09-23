"""
Does naming the document's subject entity in the query hurt retrieval?

In a single-entity corpus (one company's annual report) the company
name appears on nearly every page. It therefore carries almost no
discriminative signal, but it still shifts the query embedding.

This runs a minimal-pair A/B: identical questions differing only in
"the company" vs "Microsoft". Everything else is held constant.

Usage:
    python -m evaluation.entity_name_effect <document_id>
"""

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
EVAL_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(AI_LAYER_DIR))

from app.config import settings  # noqa: E402
from app.ingestion.embedder import Embedder  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402

from evaluation.experiments.retrieval_experiments import (  # noqa: E402
    ExperimentRetriever,
    Variant,
    load_gold,
    score_case,
)


ENTITY = "Microsoft"


def to_entity_form(question: str) -> str | None:
    """Rewrite 'the company' -> the entity name. None if N/A."""

    if not re.search(r"\bthe company\b", question, re.I):
        return None

    return re.sub(
        r"\bthe company\b", ENTITY, question, flags=re.I
    )


def run(document_id: str):
    gold = load_gold(EVAL_DIR / "gold_set.json")

    pairs = []
    for case in gold:
        if case["type"] == "unanswerable":
            continue

        entity_form = to_entity_form(case["question"])
        if entity_form:
            pairs.append((case, entity_form))

    store = FAISSVectorStore(
        settings.indexes_dir / document_id
    )
    store.load()

    embedder = Embedder()
    engine = ExperimentRetriever(embedder)

    # Dense isolates the embedding effect. The rest matter because
    # production does not run dense alone - if the CrossEncoder
    # absorbs the damage, there is nothing to fix.
    architectures = [
        (
            "dense",
            "Dense only",
            Variant("d", "Dense", use_reranker=False),
        ),
        (
            "ce",
            "Dense -> CE",
            Variant("c", "CE", use_reranker=True),
        ),
        (
            "rrf",
            "Dense + CE -> RRF",
            Variant(
                "r", "RRF", use_reranker=True, use_rrf=True
            ),
        ),
        (
            "prod",
            "Production",
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

    results = {}

    for key, label, variant in architectures:
        rows = []

        for case, entity_q in pairs:
            a = score_case(
                case["primary"],
                engine.rank(
                    store, case["question"], variant
                ),
                case["acceptable"],
            )
            b = score_case(
                case["primary"],
                engine.rank(store, entity_q, variant),
                case["acceptable"],
            )

            rows.append(
                {
                    "id": case["id"],
                    "neutral_question": case["question"],
                    "entity_question": entity_q,
                    "primary": case["primary"],
                    "neutral_recall": a["recall"],
                    "entity_recall": b["recall"],
                    "neutral_pages": a["retrieved_pages"],
                    "entity_pages": b["retrieved_pages"],
                }
            )

        n = len(rows)
        results[key] = {
            "label": label,
            "neutral": sum(
                r["neutral_recall"] for r in rows
            )
            / n,
            "entity": sum(
                r["entity_recall"] for r in rows
            )
            / n,
            "degraded": sum(
                1
                for r in rows
                if r["entity_recall"] < r["neutral_recall"]
            ),
            "improved": sum(
                1
                for r in rows
                if r["entity_recall"] > r["neutral_recall"]
            ),
            "n": n,
            "rows": rows,
        }

    print("=" * 88)
    print("ENTITY-NAME EFFECT BY ARCHITECTURE")
    print(f"minimal pairs: 'the company' vs '{ENTITY}'")
    print(f"{len(pairs)} matched question pairs, top_k=5")
    print("=" * 88)
    print(
        f"{'Architecture':<22}{'neutral':>10}{'+entity':>10}"
        f"{'delta':>9}{'degraded':>11}{'improved':>10}"
    )
    print("-" * 88)

    for key, r in results.items():
        delta = (r["entity"] - r["neutral"]) * 100
        print(
            f"{r['label']:<22}{r['neutral']:>9.1%}"
            f"{r['entity']:>10.1%}{delta:>8.1f}pp"
            f"{r['degraded']:>8}/{r['n']}"
            f"{r['improved']:>7}/{r['n']}"
        )

    print("-" * 88)

    prod = results["prod"]
    if prod["entity"] >= prod["neutral"] - 0.001:
        print(
            "\n=> Production is ROBUST to the entity name.\n"
            "   The effect is real at the dense stage but absorbed "
            "downstream.\n   No mitigation needed."
        )
    else:
        print(
            f"\n=> Production DEGRADES by "
            f"{(prod['neutral'] - prod['entity']) * 100:.1f}pp. "
            "Mitigation warranted."
        )

    print("=" * 88)

    out = RESULTS_DIR / "entity_name_effect.json"
    out.write_text(
        json.dumps(
            {"entity": ENTITY, "architectures": results},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Saved: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("document_id")
    run(p.parse_args().document_id)


if __name__ == "__main__":
    main()
