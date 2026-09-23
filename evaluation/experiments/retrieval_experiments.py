"""
Controlled retrieval architecture experiments.

This harness isolates the RANKING architecture from generation.
It loads the document's FAISS index directly and runs the gold-set
questions through configurable ranking variants.

No LLM is called, so experiments are deterministic, fast and free.
Generation-dependent metrics (citation, refusal) are deliberately
NOT measured here - they are measured by the live evaluation once
a ranking architecture has been chosen.

Usage:

    python -m evaluation.retrieval_experiments <document_id>
    python -m evaluation.retrieval_experiments <document_id> --variants dense,ce,rrf
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
EVAL_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(AI_LAYER_DIR))

from app.config import settings  # noqa: E402
from app.ingestion.embedder import Embedder  # noqa: E402
from app.retrieval.retriever import Retriever  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402


# =========================================================
# Variant definition
# =========================================================


@dataclass
class Variant:
    """One ranking architecture configuration."""

    name: str
    label: str

    # Ranking signals
    use_reranker: bool = True
    use_rrf: bool = False
    use_financial: bool = False
    use_page_aware: bool = False

    # Parameters
    candidate_k: int = 50
    top_k: int = 5
    rrf_dense_weight: float = 0.70
    rrf_reranker_weight: float = 0.30
    rrf_k: int = 60
    financial_weight: float = 0.10
    max_chunks_per_page: int = 2

    notes: str = ""


# =========================================================
# Ranking engine
# =========================================================


class ExperimentRetriever:
    """
    Re-implements the production ranking stages as independently
    switchable components, reusing the production Retriever's own
    financial scoring and page-aware selection so that experiment
    results reflect the real implementation.
    """

    def __init__(self, embedder: Embedder):
        self.embedder = embedder
        # Reuse production retriever for its reranker + heuristics.
        self._prod = Retriever(embedder=embedder)

    def rank(
        self,
        vector_store: FAISSVectorStore,
        question: str,
        variant: Variant,
    ) -> list[dict]:
        question = question.strip()
        if not question:
            return []

        # ---- Stage 1: dense candidate generation ----
        query_embedding = self.embedder.embed_query(question)

        candidate_results = vector_store.search(
            query_embedding=query_embedding,
            top_k=variant.candidate_k,
        )

        if not candidate_results:
            return []

        candidates = [
            {
                "chunk": chunk,
                "dense_score": float(dense_score),
                "dense_rank": dense_rank,
            }
            for dense_rank, (chunk, dense_score) in enumerate(
                candidate_results, start=1
            )
        ]

        # ---- Stage 2: cross-encoder reranking ----
        if variant.use_reranker:
            pairs = [
                (question, c["chunk"].text) for c in candidates
            ]
            scores = [
                float(s) for s in self._prod.reranker.predict(pairs)
            ]

            for c, s in zip(candidates, scores):
                c["reranker_score"] = s

            for rank, c in enumerate(
                sorted(
                    candidates,
                    key=lambda i: i["reranker_score"],
                    reverse=True,
                ),
                start=1,
            ):
                c["reranker_rank"] = rank

        # ---- Stage 3: base score ----
        for c in candidates:
            if variant.use_rrf:
                c["base_score"] = (
                    variant.rrf_dense_weight
                    / (variant.rrf_k + c["dense_rank"])
                ) + (
                    variant.rrf_reranker_weight
                    / (variant.rrf_k + c["reranker_rank"])
                )
            elif variant.use_reranker:
                c["base_score"] = c["reranker_score"]
            else:
                c["base_score"] = c["dense_score"]

        # ---- Stage 4: financial heuristic ----
        for c in candidates:
            if variant.use_financial:
                fin = self._prod._financial_score(
                    question=question,
                    text=c["chunk"].text,
                )
            else:
                fin = 0.0

            c["financial_score"] = fin
            c["final_score"] = c["base_score"] + (
                variant.financial_weight * fin
            )

        candidates.sort(
            key=lambda i: i["final_score"], reverse=True
        )

        # ---- Stage 5: selection ----
        if variant.use_page_aware:
            original = settings.max_chunks_per_page
            settings.max_chunks_per_page = (
                variant.max_chunks_per_page
            )
            try:
                selected = self._prod._select_page_aware(
                    scored_candidates=candidates,
                    top_k=variant.top_k,
                )
            finally:
                settings.max_chunks_per_page = original
        else:
            selected = candidates[: variant.top_k]

        return selected


# =========================================================
# Metrics
# =========================================================


def _dcg(gains: list[float]) -> float:
    return sum(
        g / math.log2(i + 2) for i, g in enumerate(gains)
    )


# Graded relevance used for nDCG when a gold set distinguishes
# required evidence from merely-valid supporting evidence.
GAIN_PRIMARY = 1.0
GAIN_ACCEPTABLE = 0.5


def load_gold(path: Path) -> list[dict]:
    """
    Load either gold-set schema and normalize to a common shape.

    v1: a JSON list of cases with `expected_pages`.
    v2: a JSON object with `cases`, each having `primary_pages`
        and `acceptable_pages`.

    Normalized case:
        {id, question, type, primary, acceptable}
    """

    data = json.loads(path.read_text(encoding="utf-8"))

    raw = data["cases"] if isinstance(data, dict) else data

    cases = []

    for case in raw:

        if "primary_pages" in case:
            primary = list(case.get("primary_pages", []))
            acceptable = list(
                case.get("acceptable_pages", [])
            )
        else:
            primary = list(case.get("expected_pages", []))
            acceptable = []

        cases.append(
            {
                "id": case["id"],
                "question": case["question"],
                "type": case.get("type"),
                "primary": primary,
                "acceptable": acceptable,
            }
        )

    return cases


def score_case(
    expected_pages: list[int],
    ranked: list[dict],
    acceptable_pages: list[int] | None = None,
) -> dict:
    """
    Compute page-level and rank-sensitive retrieval metrics
    for a single answerable case.

    `expected_pages` is the required (primary) evidence.
    `acceptable_pages` is evidence that genuinely supports the
    answer but is not required; it is excluded from the false
    positives counted against adjusted precision.

    With no acceptable pages, adjusted precision is identical to
    page precision, so v1 gold sets score exactly as before.
    """

    expected = set(expected_pages)
    acceptable = set(acceptable_pages or ()) - expected

    ranked_pages = [c["chunk"].page_number for c in ranked]
    retrieved = set(ranked_pages)

    hit = bool(expected & retrieved)

    recall = (
        len(expected & retrieved) / len(expected)
        if expected
        else 0.0
    )
    precision = (
        len(expected & retrieved) / len(retrieved)
        if retrieved
        else 0.0
    )

    # Credits any genuinely supporting page rather than treating
    # unlabelled-but-valid evidence as an error.
    adjusted_precision = (
        len(retrieved & (expected | acceptable))
        / len(retrieved)
        if retrieved
        else 0.0
    )

    exact = expected == retrieved

    # Rank-sensitive metrics over the ranked chunk list.
    # MRR uses primary evidence only; nDCG uses graded gains.
    rels = [
        1.0 if p in expected else 0.0 for p in ranked_pages
    ]

    gains = [
        GAIN_PRIMARY
        if p in expected
        else (GAIN_ACCEPTABLE if p in acceptable else 0.0)
        for p in ranked_pages
    ]

    rr = 0.0
    for i, r in enumerate(rels):
        if r > 0:
            rr = 1.0 / (i + 1)
            break

    # Ideal ranking: all relevant chunks first. The number of
    # relevant chunks available in this ranking bounds the ideal.
    ideal = sorted(rels, reverse=True)
    idcg = _dcg(ideal)
    ndcg = _dcg(rels) / idcg if idcg > 0 else 0.0

    ideal_g = sorted(gains, reverse=True)
    idcg_g = _dcg(ideal_g)
    ndcg_graded = (
        _dcg(gains) / idcg_g if idcg_g > 0 else 0.0
    )

    # Page-level rank of the first expected page found.
    first_rel_rank = next(
        (i + 1 for i, r in enumerate(rels) if r > 0), None
    )

    return {
        "hit": hit,
        "recall": recall,
        "precision": precision,
        "adjusted_precision": adjusted_precision,
        "exact": exact,
        "mrr": rr,
        "ndcg": ndcg,
        "ndcg_graded": ndcg_graded,
        "first_relevant_rank": first_rel_rank,
        "retrieved_pages": sorted(retrieved),
        "ranked_pages": ranked_pages,
    }


# =========================================================
# Variants under test
# =========================================================


def build_variants() -> list[Variant]:
    return [
        Variant(
            name="dense",
            label="A. Dense only",
            use_reranker=False,
            notes="FAISS top-5 directly. No reranking.",
        ),
        Variant(
            name="ce",
            label="B. Dense -> CrossEncoder",
            use_reranker=True,
            notes="50 candidates reranked by CE, top-5.",
        ),
        Variant(
            name="rrf",
            label="C. Dense + CE -> RRF",
            use_reranker=True,
            use_rrf=True,
            notes="RRF fusion 0.70/0.30, no financial, no page-aware.",
        ),
        Variant(
            name="ce_fin",
            label="D. CE + financial",
            use_reranker=True,
            use_financial=True,
            notes="Isolates financial heuristic on top of CE.",
        ),
        Variant(
            name="rrf_fin",
            label="E. RRF + financial",
            use_reranker=True,
            use_rrf=True,
            use_financial=True,
            notes="Production minus page-aware selection.",
        ),
        Variant(
            name="rrf_fin_page",
            label="F. RRF + financial + page-aware (PRODUCTION)",
            use_reranker=True,
            use_rrf=True,
            use_financial=True,
            use_page_aware=True,
            notes="Exact current production architecture.",
        ),
        Variant(
            name="ce_page",
            label="G. CE + page-aware",
            use_reranker=True,
            use_page_aware=True,
            notes="CE reranking with page diversity, no RRF/financial.",
        ),
        Variant(
            name="rrf_ce_heavy",
            label="H. RRF weighted toward CE (0.30/0.70)",
            use_reranker=True,
            use_rrf=True,
            rrf_dense_weight=0.30,
            rrf_reranker_weight=0.70,
            notes="Tests whether RRF weighting direction matters.",
        ),
    ]


# =========================================================
# Runner
# =========================================================


def run(
    document_id: str,
    variant_names: list[str] | None,
    gold_path: Path | None = None,
    output_path: Path | None = None,
):
    gold_path = gold_path or (EVAL_DIR / "gold_set.json")

    gold = load_gold(gold_path)

    answerable = [
        c for c in gold if c.get("type") != "unanswerable"
    ]

    index_dir = settings.indexes_dir / document_id
    vector_store = FAISSVectorStore(index_dir)
    vector_store.load()

    print(f"Index: {index_dir}")
    print(f"Chunks: {len(vector_store.chunks)}")
    print(f"Gold set: {gold_path.name}")
    print(f"Answerable gold cases: {len(answerable)}\n")

    embedder = Embedder()
    engine = ExperimentRetriever(embedder)

    variants = build_variants()
    if variant_names:
        variants = [
            v for v in variants if v.name in variant_names
        ]

    all_results = {}

    for variant in variants:
        print(f"Running: {variant.label}")

        per_case = []

        for case in answerable:
            ranked = engine.rank(
                vector_store=vector_store,
                question=case["question"],
                variant=variant,
            )

            metrics = score_case(
                expected_pages=case["primary"],
                ranked=ranked,
                acceptable_pages=case["acceptable"],
            )

            metrics["id"] = case["id"]
            metrics["question"] = case["question"]
            metrics["expected_pages"] = case["primary"]
            metrics["acceptable_pages"] = case["acceptable"]

            per_case.append(metrics)

        n = len(per_case)
        summary = {
            "hit_rate": sum(c["hit"] for c in per_case) / n,
            "recall": sum(c["recall"] for c in per_case) / n,
            "precision": sum(
                c["precision"] for c in per_case
            )
            / n,
            "adjusted_precision": sum(
                c["adjusted_precision"] for c in per_case
            )
            / n,
            "exact": sum(c["exact"] for c in per_case) / n,
            "mrr": sum(c["mrr"] for c in per_case) / n,
            "ndcg": sum(c["ndcg"] for c in per_case) / n,
            "ndcg_graded": sum(
                c["ndcg_graded"] for c in per_case
            )
            / n,
        }

        all_results[variant.name] = {
            "label": variant.label,
            "notes": variant.notes,
            "config": {
                "use_reranker": variant.use_reranker,
                "use_rrf": variant.use_rrf,
                "use_financial": variant.use_financial,
                "use_page_aware": variant.use_page_aware,
                "candidate_k": variant.candidate_k,
                "top_k": variant.top_k,
                "rrf_dense_weight": variant.rrf_dense_weight,
                "rrf_reranker_weight": (
                    variant.rrf_reranker_weight
                ),
            },
            "summary": summary,
            "cases": per_case,
        }

    # ---- Comparison table ----
    print("\n" + "=" * 100)
    print("RETRIEVAL ARCHITECTURE COMPARISON")
    print(
        f"(document={document_id}, "
        f"{len(answerable)} answerable cases, top_k=5)"
    )
    print("=" * 100)

    header = (
        f"{'Architecture':<46} {'Hit@5':>7} {'Rec@5':>7} "
        f"{'Prec@5':>7} {'AdjP@5':>7} {'MRR':>7} "
        f"{'nDCG':>7} {'nDCGg':>7}"
    )
    print(header)
    print("-" * 100)

    for name, data in all_results.items():
        s = data["summary"]
        print(
            f"{data['label']:<46} "
            f"{s['hit_rate']:>6.1%} "
            f"{s['recall']:>6.1%} "
            f"{s['precision']:>6.1%} "
            f"{s['adjusted_precision']:>6.1%} "
            f"{s['mrr']:>6.3f} "
            f"{s['ndcg']:>6.3f} "
            f"{s['ndcg_graded']:>6.3f}"
        )

    print("=" * 100)

    out = output_path or (
        RESULTS_DIR / "retrieval_experiment_results.json"
    )
    out.write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")

    return all_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("document_id")
    parser.add_argument(
        "--variants",
        default=None,
        help="Comma-separated variant names to run.",
    )
    parser.add_argument(
        "--gold",
        default=None,
        help="Gold set file (v1 list or v2 object schema).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Where to write results JSON.",
    )
    args = parser.parse_args()

    names = (
        [v.strip() for v in args.variants.split(",")]
        if args.variants
        else None
    )

    run(
        args.document_id,
        names,
        gold_path=Path(args.gold) if args.gold else None,
        output_path=Path(args.out) if args.out else None,
    )


if __name__ == "__main__":
    main()
