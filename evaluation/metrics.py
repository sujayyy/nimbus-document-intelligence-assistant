from typing import Iterable


def page_recall(
    expected_pages: Iterable[int],
    retrieved_pages: Iterable[int],
) -> float:
    """
    Calculate how many expected pages were successfully retrieved.

    This metric is intended for answerable questions.

    Example:
        expected_pages = [36, 71]
        retrieved_pages = [35, 36, 70, 71]

        Result = 1.0
    """

    expected = set(expected_pages)
    retrieved = set(retrieved_pages)

    if not expected:
        return 0.0

    return len(expected & retrieved) / len(expected)


def page_precision(
    expected_pages: Iterable[int],
    retrieved_pages: Iterable[int],
) -> float:
    """
    Calculate how many retrieved pages were actually expected.

    Example:
        expected_pages = [36, 71]
        retrieved_pages = [36, 71, 80]

        Result = 2 / 3
    """

    expected = set(expected_pages)
    retrieved = set(retrieved_pages)

    if not retrieved:
        return 0.0

    if not expected:
        return 0.0

    return len(expected & retrieved) / len(retrieved)


def citation_precision(
    cited_pages: Iterable[int],
    retrieved_pages: Iterable[int],
) -> float:
    """
    Calculate the percentage of cited pages that actually
    came from the retrieved pages.

    If no citations were produced, return 0.0 because
    there is no evidence of citation correctness.
    """

    cited = list(cited_pages)
    retrieved = set(retrieved_pages)

    if not cited:
        return 0.0

    valid_citations = sum(
        1
        for page in cited
        if page in retrieved
    )

    return valid_citations / len(cited)


def citation_recall(
    cited_pages: Iterable[int],
    expected_pages: Iterable[int],
) -> float:
    """
    Calculate how many expected pages were actually cited.

    This metric is intended for answerable questions.
    """

    cited = set(cited_pages)
    expected = set(expected_pages)

    if not expected:
        return 0.0

    return len(cited & expected) / len(expected)


def exact_page_match(
    expected_pages: Iterable[int],
    retrieved_pages: Iterable[int],
) -> bool:
    """
    Check whether the retrieved page set exactly matches
    the expected page set.

    This metric is intended for answerable questions.
    """

    expected = set(expected_pages)
    retrieved = set(retrieved_pages)

    if not expected:
        return False

    return expected == retrieved


def refusal_correct(
    question_type: str,
    answer: str,
) -> bool:
    """
    Check whether the system correctly refused an
    unanswerable question.

    A question is considered correctly refused when:

        question_type == "unanswerable"

    and the generated answer contains one of the
    expected refusal patterns.
    """

    if question_type != "unanswerable":
        return False

    answer_lower = answer.lower().strip()

    refusal_patterns = [
        "i don't have enough information",
        "does not contain",
        "cannot be determined from the document",
        "cannot be determined from the provided document",
        "couldn't produce a verifiable answer",
        "not contain enough information",
        "information cannot be determined",
    ]

    return any(
        pattern in answer_lower
        for pattern in refusal_patterns
    )