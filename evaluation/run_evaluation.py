import json
import re
from pathlib import Path

from evaluation.evaluator import evaluate_case


EVALUATION_DIR = Path(__file__).resolve().parent

GOLD_SET_PATH = EVALUATION_DIR / "gold_set.json"
LIVE_RESULTS_PATH = EVALUATION_DIR / "live_results.json"


PAGE_CITATION_PATTERN = re.compile(
    r"\[Page\s+(\d+)\]"
)


def load_json(path: Path):
    """Load JSON data from a file."""

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def extract_cited_pages(answer: str) -> list[int]:
    """
    Extract page numbers from citations such as:

        [Page 36]
        [Page 71]

    Returns a sorted list of unique page numbers.
    """

    return sorted(
        {
            int(page)
            for page in PAGE_CITATION_PATTERN.findall(
                answer or ""
            )
        }
    )


def build_gold_lookup(
    gold_set: list[dict],
) -> dict:
    """Create a lookup dictionary using test-case IDs."""

    return {
        case["id"]: case
        for case in gold_set
    }


def evaluate_live_results(
    gold_set: list[dict],
    live_results: list[dict],
) -> list[dict]:
    """
    Compare live RAG results against the gold set.
    """

    gold_lookup = build_gold_lookup(gold_set)

    evaluation_results = []

    for result in live_results:

        case_id = result["id"]

        if case_id not in gold_lookup:
            continue

        gold_case = gold_lookup[case_id]

        question_type = gold_case.get(
            "type",
            "factual",
        )

        expected_pages = gold_case.get(
            "expected_pages",
            [],
        )

        retrieved_pages = result.get(
            "retrieved_pages",
            [],
        )

        answer = result.get(
            "answer",
            "",
        )

        cited_pages = extract_cited_pages(
            answer
        )

        metrics = evaluate_case(
            question_type=question_type,
            expected_pages=expected_pages,
            retrieved_pages=retrieved_pages,
            cited_pages=cited_pages,
            answer=answer,
        )

        evaluation_results.append(
            {
                "id": case_id,
                "question": result.get(
                    "question",
                    gold_case.get(
                        "question",
                        "",
                    ),
                ),
                "type": question_type,
                "expected_pages": expected_pages,
                "retrieved_pages": retrieved_pages,
                "cited_pages": cited_pages,
                "metrics": metrics,
                "answer": answer,
            }
        )

    return evaluation_results


def calculate_average(
    results: list[dict],
    metric_name: str,
) -> float:
    """
    Calculate the average of a metric across
    answerable evaluation cases.
    """

    values = [
        result["metrics"][metric_name]
        for result in results
        if metric_name in result["metrics"]
    ]

    if not values:
        return 0.0

    return sum(values) / len(values)


def calculate_exact_match_rate(
    results: list[dict],
) -> float:
    """
    Calculate exact page match rate for answerable
    evaluation cases.
    """

    values = [
        result["metrics"]["exact_page_match"]
        for result in results
        if "exact_page_match" in result["metrics"]
    ]

    if not values:
        return 0.0

    matches = sum(
        1
        for value in values
        if value
    )

    return matches / len(values)


def calculate_refusal_rate(
    results: list[dict],
) -> float:
    """
    Calculate the percentage of unanswerable
    questions that were correctly refused.
    """

    values = [
        result["metrics"]["refusal_correct"]
        for result in results
        if "refusal_correct" in result["metrics"]
    ]

    if not values:
        return 0.0

    correct_refusals = sum(
        1
        for value in values
        if value
    )

    return correct_refusals / len(values)


def print_results(
    results: list[dict],
) -> None:
    """Print detailed evaluation results."""

    print("\n")
    print("Document Intelligence Assistant")
    print("Phase 3 - Evaluation Results")
    print("=" * 70)

    for result in results:

        print(
            f"\nID: {result['id']}"
        )

        print(
            f"Question: {result['question']}"
        )

        print(
            f"Type: {result['type']}"
        )

        print(
            f"Expected Pages: "
            f"{result['expected_pages']}"
        )

        print(
            f"Retrieved Pages: "
            f"{result['retrieved_pages']}"
        )

        print(
            f"Cited Pages: "
            f"{result['cited_pages']}"
        )

        print(
            f"Metrics: "
            f"{result['metrics']}"
        )

    print("\n")
    print("=" * 70)
    print("Overall Evaluation")
    print("=" * 70)

    print(
        f"Average Page Recall: "
        f"{calculate_average(results, 'page_recall'):.3f}"
    )

    print(
        f"Average Page Precision: "
        f"{calculate_average(results, 'page_precision'):.3f}"
    )

    print(
        f"Exact Page Match Rate: "
        f"{calculate_exact_match_rate(results):.3f}"
    )

    print(
        f"Average Citation Precision: "
        f"{calculate_average(results, 'citation_precision'):.3f}"
    )

    print(
        f"Average Citation Recall: "
        f"{calculate_average(results, 'citation_recall'):.3f}"
    )

    print(
        f"Correct Refusal Rate: "
        f"{calculate_refusal_rate(results):.3f}"
    )

    print("=" * 70)


def save_results(
    results: list[dict],
    output_path: Path,
) -> None:
    """Save detailed evaluation results."""

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
    """Run the complete evaluation."""

    if not GOLD_SET_PATH.exists():
        raise FileNotFoundError(
            f"Gold set not found: "
            f"{GOLD_SET_PATH}"
        )

    if not LIVE_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Live results not found: "
            f"{LIVE_RESULTS_PATH}\n"
            "Run run_live_evaluation.py first."
        )

    gold_set = load_json(
        GOLD_SET_PATH
    )

    live_results = load_json(
        LIVE_RESULTS_PATH
    )

    if not isinstance(
        gold_set,
        list,
    ):
        raise ValueError(
            "gold_set.json must contain "
            "a JSON list."
        )

    if not isinstance(
        live_results,
        list,
    ):
        raise ValueError(
            "live_results.json must contain "
            "a JSON list."
        )

    results = evaluate_live_results(
        gold_set,
        live_results,
    )

    print_results(
        results
    )

    output_path = (
        EVALUATION_DIR
        / "evaluation_results.json"
    )

    save_results(
        results,
        output_path,
    )

    print(
        f"\nDetailed results saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()