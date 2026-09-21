from evaluation.metrics import (
    page_recall,
    page_precision,
    citation_precision,
    citation_recall,
    exact_page_match,
    refusal_correct,
)


def evaluate_retrieval(
    expected_pages,
    retrieved_pages,
) -> dict:
    """
    Evaluate retrieval quality for an answerable question.
    """

    expected_pages = list(expected_pages)
    retrieved_pages = list(retrieved_pages)

    return {
        "page_recall": page_recall(
            expected_pages,
            retrieved_pages,
        ),
        "page_precision": page_precision(
            expected_pages,
            retrieved_pages,
        ),
        "exact_page_match": exact_page_match(
            expected_pages,
            retrieved_pages,
        ),
    }


def evaluate_citations(
    expected_pages,
    retrieved_pages,
    cited_pages,
) -> dict:
    """
    Evaluate citation quality for an answerable question.
    """

    expected_pages = list(expected_pages)
    retrieved_pages = list(retrieved_pages)
    cited_pages = list(cited_pages)

    return {
        "citation_precision": citation_precision(
            cited_pages,
            retrieved_pages,
        ),
        "citation_recall": citation_recall(
            cited_pages,
            expected_pages,
        ),
    }


def evaluate_refusal(
    question_type: str,
    answer: str,
) -> dict:
    """
    Evaluate whether the system correctly refused
    an unanswerable question.
    """

    return {
        "refusal_correct": refusal_correct(
            question_type,
            answer,
        )
    }


def evaluate_case(
    question_type: str,
    expected_pages,
    retrieved_pages,
    cited_pages,
    answer: str,
) -> dict:
    """
    Evaluate one complete test case.

    Answerable questions are evaluated using retrieval
    and citation metrics.

    Unanswerable questions are evaluated using refusal
    correctness.
    """

    if question_type == "unanswerable":
        return evaluate_refusal(
            question_type=question_type,
            answer=answer,
        )

    retrieval = evaluate_retrieval(
        expected_pages=expected_pages,
        retrieved_pages=retrieved_pages,
    )

    citations = evaluate_citations(
        expected_pages=expected_pages,
        retrieved_pages=retrieved_pages,
        cited_pages=cited_pages,
    )

    return {
        **retrieval,
        **citations,
    }