"""
Nimbus evaluation.

Scores a live run against a gold set and reports a three-tier scorecard:

    ANSWER QUALITY       what the user actually gets - the product goal
    RETRIEVAL DIAGNOSTICS useful for debugging, not optimisation targets
    RETIRED               kept for continuity, each annotated with why it
                          cannot be used as a target

The tiering is not cosmetic. Three of the original six metrics cannot be
improved by better retrieval:

  * Page Precision is bounded by mean(|expected pages|) / |pages returned|.
  * Exact Page Match requires |expected| >= the number of distinct pages
    top_k chunks must span, which is false for almost every case.
  * Citation Precision is enforced by query_pipeline.py, which replaces an
    answer with a refusal when its citations fail validation - so every
    surviving answer scores 1.0 by construction.

Both ceilings are computed from the data below rather than asserted.

Usage:
    python -m evaluation.run_evaluation
"""

import argparse
import json
import re
from pathlib import Path

from evaluation.answer_metrics import (
    answer_accuracy,
    is_refusal,
    numeric_grounding,
    ungrounded_figures,
)
from evaluation.metrics import (
    citation_precision,
    citation_recall,
    exact_page_match,
    page_precision,
    page_recall,
)


EVALUATION_DIR = Path(__file__).resolve().parent

GOLD_SET_PATH = EVALUATION_DIR / "gold_set.json"
LIVE_RESULTS_PATH = EVALUATION_DIR / "live_results.json"

PAGE_CITATION_PATTERN = re.compile(r"\[Page\s+(\d+)\]")


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------


def extract_cited_pages(answer: str) -> list[int]:
    """Page numbers cited in an answer, e.g. [Page 36]."""

    return sorted(
        {
            int(page)
            for page in PAGE_CITATION_PATTERN.findall(
                answer or ""
            )
        }
    )


def load_gold(path: Path) -> dict:
    """Load the gold set, keyed by case id."""

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data["cases"] if isinstance(data, dict) else data

    return {
        case["id"]: {
            "question": case["question"],
            "type": case.get("type", "factual"),
            "answer": case.get("answer", ""),
            "primary": case.get(
                "primary_pages",
                case.get("expected_pages", []),
            ),
            "acceptable": case.get(
                "acceptable_pages", []
            ),
        }
        for case in raw
    }


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------


def score(gold: dict, live: list[dict]) -> list[dict]:
    rows = []

    for result in live:
        case = gold.get(result["id"])

        if not case:
            continue

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        texts = [s.get("text", "") for s in sources]

        retrieved = sorted(
            set(result.get("retrieved_pages", []))
        )
        primary = list(case["primary"])
        acceptable = [
            p
            for p in case["acceptable"]
            if p not in primary
        ]

        cited = extract_cited_pages(answer)

        row = {
            "id": result["id"],
            "type": case["type"],
            "question": case["question"],
            "expected_pages": primary,
            "acceptable_pages": acceptable,
            "retrieved_pages": retrieved,
            "cited_pages": cited,
            "answer": answer,
            "refused": is_refusal(answer),
            # Page per returned chunk, duplicates kept - needed to
            # derive the structural page-metric ceilings below.
            "source_pages": [
                s.get("page_number")
                for s in sources
                if s.get("page_number") is not None
            ],
        }

        if case["type"] == "unanswerable":
            # Uses the answer-level detector, which accounts for
            # citations and position: a refusal that cites evidence
            # to explain the gap still counts as a refusal.
            row["refusal_correct"] = row["refused"]
            rows.append(row)
            continue

        accuracy, mode = answer_accuracy(
            case["answer"], answer
        )

        allowed = set(primary) | set(acceptable)

        row.update(
            {
                "answer_accuracy": accuracy,
                "accuracy_mode": mode,
                "numeric_grounding": numeric_grounding(
                    answer, texts
                ),
                "ungrounded_figures": ungrounded_figures(
                    answer, texts
                ),
                "page_recall": page_recall(
                    primary, retrieved
                ),
                "page_precision": page_precision(
                    primary, retrieved
                ),
                "adjusted_page_precision": (
                    len(set(retrieved) & allowed)
                    / len(retrieved)
                    if retrieved
                    else 0.0
                ),
                "exact_page_match": exact_page_match(
                    primary, retrieved
                ),
                "citation_precision": citation_precision(
                    cited, retrieved
                ),
                "citation_recall": citation_recall(
                    cited, primary
                ),
            }
        )

        rows.append(row)

    return rows


def mean(rows: list[dict], key: str) -> float:
    values = [
        r[key]
        for r in rows
        if r.get(key) is not None
    ]
    return sum(values) / len(values) if values else 0.0


def ceilings(answerable: list[dict]) -> dict:
    """
    Derive the arithmetic limits of the page-level metrics from the
    data, so the caveats printed below are computed, not asserted.

    The exact-match bound is structural rather than observed: k chunks
    capped at `max_per_page` from any one page must span at least
    ceil(k / max_per_page) distinct pages, so exact match is impossible
    whenever a case expects fewer pages than that - however the ranking
    behaves. Using the smallest page count that happened to occur would
    understate what the metric could ever reach.
    """

    from math import ceil

    sizes = [
        len(r["retrieved_pages"])
        for r in answerable
        if r["retrieved_pages"]
    ]

    mean_pages = (
        sum(sizes) / len(sizes) if sizes else 0
    )

    chunk_counts = [
        len(r["source_pages"])
        for r in answerable
        if r["source_pages"]
    ]
    top_k = max(chunk_counts) if chunk_counts else 0

    max_per_page = 1
    for r in answerable:
        pages = r["source_pages"]
        for page in set(pages):
            max_per_page = max(
                max_per_page, pages.count(page)
            )

    min_pages = (
        ceil(top_k / max_per_page) if top_k else 0
    )

    mean_expected = sum(
        len(r["expected_pages"]) for r in answerable
    ) / len(answerable)

    exact_possible = sum(
        1
        for r in answerable
        if len(r["expected_pages"]) >= min_pages
    )

    return {
        "precision_ceiling": (
            mean_expected / mean_pages
            if mean_pages
            else 0.0
        ),
        "exact_ceiling": exact_possible
        / len(answerable),
        "min_pages": min_pages,
        "top_k": top_k,
        "max_per_page": max_per_page,
    }


# ---------------------------------------------------------
# Reporting
# ---------------------------------------------------------


def print_scorecard(
    rows: list[dict], gold_name: str, live_name: str
) -> None:
    answerable = [
        r for r in rows if r["type"] != "unanswerable"
    ]
    unanswerable = [
        r for r in rows if r["type"] == "unanswerable"
    ]

    lim = ceilings(answerable)

    answered = sum(
        1 for r in answerable if not r["refused"]
    )

    print("\n" + "=" * 72)
    print("Nimbus Evaluation")
    print("=" * 72)
    print(f"gold: {gold_name}   live: {live_name}")
    print(
        f"cases: {len(answerable)} answerable, "
        f"{len(unanswerable)} unanswerable"
    )

    print("\n" + "-" * 72)
    print("ANSWER QUALITY        (primary - what the user gets)")
    print("-" * 72)
    print(
        f"  Answer Accuracy       : "
        f"{mean(answerable, 'answer_accuracy'):.3f}"
        f"   (floor; term-mode penalises paraphrase)"
    )
    print(
        f"  Numeric Grounding     : "
        f"{mean(answerable, 'numeric_grounding'):.3f}"
        f"   (1.000 = no fabricated figures)"
    )
    print(
        f"  Answer Rate           : "
        f"{answered / len(answerable):.3f}"
        f"   ({answered}/{len(answerable)})"
    )
    print(
        f"  Correct Refusal Rate  : "
        f"{mean(unanswerable, 'refusal_correct'):.3f}"
        f"   ({len(unanswerable)} cases)"
    )

    print("\n" + "-" * 72)
    print("RETRIEVAL DIAGNOSTICS (debugging aids, not targets)")
    print("-" * 72)
    print(
        f"  Page Recall           : "
        f"{mean(answerable, 'page_recall'):.3f}"
    )
    print(
        f"  Page Precision (adj)  : "
        f"{mean(answerable, 'adjusted_page_precision'):.3f}"
        f"   (credits valid supporting pages)"
    )
    print(
        f"  Citation Recall       : "
        f"{mean(answerable, 'citation_recall'):.3f}"
    )

    print("\n" + "-" * 72)
    print("RETIRED               (cannot be improved by retrieval)")
    print("-" * 72)
    print(
        f"  Page Precision (raw)  : "
        f"{mean(answerable, 'page_precision'):.3f}"
        f"   ceiling {lim['precision_ceiling']:.3f}"
    )
    print(
        f"  Exact Page Match      : "
        f"{sum(1 for r in answerable if r['exact_page_match']) / len(answerable):.3f}"
        f"   max achievable {lim['exact_ceiling']:.3f}"
    )
    print(
        f"                          "
        f"{lim['top_k']} chunks at <={lim['max_per_page']}/page span "
        f">={lim['min_pages']} pages, so a case needs "
        f">={lim['min_pages']} expected pages to ever match"
    )
    print(
        f"  Citation Precision    : "
        f"{mean(answerable, 'citation_precision'):.3f}"
        f"   enforced by the pipeline, always 1.000"
    )

    bad = [
        r
        for r in answerable
        if r.get("ungrounded_figures")
    ]
    if bad:
        print("\n  UNGROUNDED FIGURES (possible fabrication):")
        for r in bad:
            print(
                f"    case {r['id']}: {r['ungrounded_figures']}"
            )
    else:
        print(
            "\n  Every figure in every answer traces to retrieved evidence."
        )

    weak = sorted(
        (
            r
            for r in answerable
            if r["answer_accuracy"] < 0.6
        ),
        key=lambda r: r["answer_accuracy"],
    )
    if weak:
        print("\n  LOWEST ANSWER ACCURACY:")
        for r in weak:
            print(
                f"    case {r['id']} ({r['accuracy_mode']}): "
                f"{r['answer_accuracy']:.2f}  "
                f"{r['question'][:44]}"
            )

    print("=" * 72)



# ---------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold", default=str(GOLD_SET_PATH)
    )
    parser.add_argument(
        "--live", default=str(LIVE_RESULTS_PATH)
    )
    parser.add_argument(
        "--out",
        default=str(
            EVALUATION_DIR / "evaluation_results.json"
        ),
    )
    args = parser.parse_args()

    gold_path = Path(args.gold)
    live_path = Path(args.live)

    if not gold_path.exists():
        raise FileNotFoundError(
            f"Gold set not found: {gold_path}"
        )

    if not live_path.exists():
        raise FileNotFoundError(
            f"Live results not found: {live_path}\n"
            "Run run_live_evaluation.py first."
        )

    rows = score(
        load_gold(gold_path),
        json.loads(
            live_path.read_text(encoding="utf-8")
        ),
    )

    print_scorecard(
        rows, gold_path.name, live_path.name
    )

    Path(args.out).write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDetailed results saved to: {args.out}")


if __name__ == "__main__":
    main()
