"""
Answer-level metrics.

The existing metrics measure retrieval and citation bookkeeping. None of
them checks whether the answer is correct, even though the gold set
carries a correct answer for every case.

These close that gap, and they are deterministic - no LLM judge, so they
are free, reproducible, and cannot drift.

    answer_accuracy    did the answer state the facts the gold answer states?
    numeric_grounding  is every figure in the answer traceable to retrieved text?
    answered           did it answer at all, rather than refuse?

`numeric_grounding` is the hallucination check that citation_precision
only appears to be: citation_precision is enforced by the pipeline (an
answer whose citations fail validation is replaced by a refusal), so it
is always 1.0 by construction. Grounding instead asks whether the
*numbers* came from the evidence.
"""

import re


# [Page 36] style citations must be stripped before figures are read,
# or page numbers would be scored as facts.
CITATION_RE = re.compile(r"\[Page\s+\d+\]", re.I)

# 281,724 | $281.7 | 15% | 2025
FIGURE_RE = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*%?")

# Chunk text comes from tokenizer.decode(), which inserts a space after
# in-number punctuation: "101, 832" and "13. 70". Left as-is these parse
# as separate figures, so grounded numbers would be reported as
# fabrications. Rejoin them before any figure is read.
SPACED_COMMA_RE = re.compile(r"(\d),\s+(?=\d{3}\b)")
SPACED_POINT_RE = re.compile(r"(\d)\.\s+(?=\d)")


def normalize_number_spacing(text: str) -> str:
    text = SPACED_COMMA_RE.sub(r"\1,", text or "")
    return SPACED_POINT_RE.sub(r"\1.", text)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were",
    "are", "its", "has", "have", "had", "his", "her", "their", "our",
    "company", "companys", "document", "report", "million", "billion",
    "fiscal", "year", "years", "compared", "approximately", "including",
    "provides", "describes", "identifies", "information", "about",
    "across", "which", "also", "such", "than", "into", "over", "other",
    "these", "they", "them", "there", "where", "when", "what",
}

REFUSAL_MARKERS = (
    "don't have enough information",
    "does not contain",
    "does not provide",
    "cannot be determined",
    "couldn't produce a verifiable",
    "not contain enough information",
    "no information",
)


# Markdown ordered-list markers ("1." at the start of a line) are
# formatting, not claims. Counted as figures they look like ungrounded
# assertions of the numbers 1, 2, 3.
LIST_MARKER_RE = re.compile(r"^\s*\d+\.\s+", re.M)


def strip_citations(text: str) -> str:
    return CITATION_RE.sub(" ", text or "")


def strip_list_markers(text: str) -> str:
    return LIST_MARKER_RE.sub(" ", text or "")


def extract_figures(text: str) -> set[float]:
    """Numeric values in the text, citations removed."""

    out = set()

    cleaned = normalize_number_spacing(
        strip_list_markers(strip_citations(text))
    )

    for raw in FIGURE_RE.findall(cleaned):
        try:
            out.add(float(raw.replace(",", "")))
        except ValueError:
            continue

    return out


def extract_terms(text: str) -> set[str]:
    """Content words, for gold answers that carry no figures."""

    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text or "")

    return {
        w.lower()
        for w in words
        if w.lower() not in STOPWORDS
    }


def is_refusal(answer: str) -> bool:
    """
    True only when the response declines to answer.

    A cited answer that ends with a caveat - "...the evidence does not
    provide further detail on X [Page 77]" - is an answer, and a
    well-behaved one. Both pipeline refusals and model refusals carry
    no page citations, because there is nothing to cite, so the presence
    of a citation settles it.
    """

    text = answer or ""
    low = text.lower()

    hits = [
        low.find(m) for m in REFUSAL_MARKERS if m in low
    ]

    if not hits:
        return False

    # No citations at all: both pipeline and model refusals look
    # like this, because there is nothing to cite.
    if not CITATION_RE.search(text):
        return True

    # Otherwise position decides. A refusal leads with the refusal
    # ("The information cannot be determined from the document..."),
    # even when it cites evidence to explain the gap. An answer leads
    # with the answer and caveats what it could not cover at the end.
    return min(hits) <= LEADING_WINDOW


# How far into an answer a refusal marker still counts as "leading".
LEADING_WINDOW = 150


def _matches(value: float, pool: set[float]) -> bool:
    """
    True if `value` is in `pool`, allowing for rounding and unit
    rescaling - "$281.7 billion" is a faithful restatement of a
    281,724 million figure, not a fabrication.
    """

    for source in pool:
        for scale in (1.0, 1000.0, 0.001):
            scaled = source * scale
            tolerance = max(abs(scaled) * 0.005, 0.01)

            if abs(value - scaled) <= tolerance:
                return True

    return False


def answer_accuracy(
    gold_answer: str,
    generated_answer: str,
) -> tuple[float, str]:
    """
    Fraction of the gold answer's key facts present in the generated
    answer. Uses figures when the gold answer has them, otherwise
    content-word overlap.

    Returns (score, mode).
    """

    if is_refusal(generated_answer):
        return 0.0, "refused"

    gold_figures = extract_figures(gold_answer)

    if gold_figures:
        got = extract_figures(generated_answer)

        hits = sum(
            1 for f in gold_figures if _matches(f, got)
        )

        return hits / len(gold_figures), "figures"

    gold_terms = extract_terms(gold_answer)

    if not gold_terms:
        return 0.0, "empty"

    got_terms = extract_terms(generated_answer)

    return (
        len(gold_terms & got_terms) / len(gold_terms),
        "terms",
    )


def _is_derived(value: float, pool: set[float]) -> bool:
    """
    True if `value` is the difference or sum of two evidence figures.

    Answers legitimately compute: "revenue increased ... an increase of
    $36,602 million" is 281,724 - 245,122. That figure is not in the
    text, but it is not invented either, and scoring it as a fabrication
    would make the metric cry wolf.
    """

    values = [v for v in pool if v >= 1.0]

    if len(values) > 400:  # keep the pairwise scan bounded
        values = sorted(values, reverse=True)[:400]

    targets = {value}

    for i, a in enumerate(values):
        for b in values[i + 1 :]:
            for cand in (a - b, b - a, a + b):
                if cand <= 0:
                    continue
                if abs(cand - value) <= max(
                    abs(value) * 0.005, 0.01
                ):
                    return True

    return False


def classify_figures(
    generated_answer: str,
    source_texts: list[str],
) -> dict:
    """
    Split the answer's figures into quoted / derived / ungrounded.

    quoted     present in the retrieved evidence
    derived    a sum or difference of two evidence figures
    ungrounded neither - the answer asserted a number it was not given
    """

    if is_refusal(generated_answer):
        return {
            "quoted": [],
            "derived": [],
            "ungrounded": [],
        }

    pool: set[float] = set()
    for text in source_texts:
        pool |= extract_figures(text)

    quoted, derived, ungrounded = [], [], []

    for f in sorted(extract_figures(generated_answer)):
        if _matches(f, pool):
            quoted.append(f)
        elif _is_derived(f, pool):
            derived.append(f)
        else:
            ungrounded.append(f)

    return {
        "quoted": quoted,
        "derived": derived,
        "ungrounded": ungrounded,
    }


def numeric_grounding(
    generated_answer: str,
    source_texts: list[str],
) -> float | None:
    """
    Fraction of figures in the answer that are traceable to the
    retrieved evidence, either quoted directly or derived from it.
    None when the answer states no figures.

    Below 1.0 means the answer asserted a number it was not given.
    """

    parts = classify_figures(
        generated_answer, source_texts
    )

    total = (
        len(parts["quoted"])
        + len(parts["derived"])
        + len(parts["ungrounded"])
    )

    if total == 0:
        return None

    return (
        len(parts["quoted"]) + len(parts["derived"])
    ) / total


def ungrounded_figures(
    generated_answer: str,
    source_texts: list[str],
) -> list[float]:
    """The specific figures that could not be traced - for diagnosis."""

    return classify_figures(
        generated_answer, source_texts
    )["ungrounded"]
