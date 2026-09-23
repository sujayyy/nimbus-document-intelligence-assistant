import json
import sys
from pathlib import Path


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
GOLD_SET_PATH = Path(__file__).resolve().parent / "gold_set.json"

# Make the existing ai-layer package importable.
sys.path.insert(0, str(AI_LAYER_DIR))


from app.pipelines.query_pipeline import QueryPipeline


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def load_gold_set(path: Path | None = None) -> list[dict]:
    """
    Load evaluation questions from a gold set.

    The gold set is an object whose `cases` key holds the list.
    """

    with open(
        path or GOLD_SET_PATH, "r", encoding="utf-8"
    ) as file:
        data = json.load(file)

    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]

    if not isinstance(data, list):
        raise ValueError(
            "Gold set must be a JSON list, or an object with a "
            "'cases' list."
        )

    return data


def run_live_evaluation(
    document_id: str,
    gold_path: Path | None = None,
) -> list[dict]:
    """
    Run every gold-set question through the real QueryPipeline.

    This function does NOT calculate evaluation scores yet.
    It collects the actual RAG output so we can verify:
        - generated answer
        - retrieved pages
        - citation pages
        - retrieval scores
    """

    gold_set = load_gold_set(gold_path)

    pipeline = QueryPipeline()

    results = []

    for case in gold_set:
        case_id = case["id"]
        question = case["question"]

        print(f"\n{'=' * 70}")
        print(f"Running test case {case_id}")
        print(f"Question: {question}")
        print("=" * 70)

        try:
            response = pipeline.run(
                document_id=document_id,
                question=question,
            )

            sources = response.get("sources", [])

            retrieved_pages = sorted(
                {
                    source["page_number"]
                    for source in sources
                    if source.get("page_number") is not None
                }
            )

            results.append(
                {
                    "id": case_id,
                    "question": question,
                    "type": case.get("type"),
                    "expected_pages": case.get(
                        "primary_pages",
                        case.get("expected_pages", []),
                    ),
                    "answer": response.get("answer", ""),
                    "retrieved_pages": retrieved_pages,
                    "sources": sources,
                }
            )

            print("\nGenerated Answer:")
            print(response.get("answer", ""))

            print("\nRetrieved Pages:")
            print(retrieved_pages)

            print("\nRetrieved Sources:")
            for source in sources:
                print(
                    f"  Page {source.get('page_number')} "
                    f"| Score: {source.get('score')}"
                )

        except Exception as exc:
            print(f"\nERROR: {exc}")

            results.append(
                {
                    "id": case_id,
                    "question": question,
                    "type": case.get("type"),
                    "expected_pages": case.get(
                        "primary_pages",
                        case.get("expected_pages", []),
                    ),
                    "answer": "",
                    "retrieved_pages": [],
                    "sources": [],
                    "error": str(exc),
                }
            )

    return results


def save_results(
    results: list[dict],
    output_path: Path,
) -> None:
    """Save live evaluation results as JSON."""

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    """
    Usage:

        python -m evaluation.run_live_evaluation <document_id>
    """

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("document_id")
    parser.add_argument(
        "--gold",
        default=None,
        help="Gold set file (v1 list or v2 object schema).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Where to write live results JSON.",
    )
    args = parser.parse_args()

    document_id = args.document_id
    gold_path = Path(args.gold) if args.gold else None

    print("\nDocument Intelligence Assistant")
    print("Phase 3 - Live Evaluation")
    print("=" * 70)
    print(f"Document ID: {document_id}")

    results = run_live_evaluation(document_id, gold_path)

    output_path = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parent
        / "live_results.json"
    )

    save_results(
        results,
        output_path,
    )

    print("\n" + "=" * 70)
    print("Live evaluation completed.")
    print(f"Results saved to: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()