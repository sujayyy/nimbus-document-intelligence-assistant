"""
Tests for subject-entity detection and query stripping.

The measurements behind this module are in its docstring: naming the
document's subject in a query drove dense recall from 61.1% to 0.0%
and production recall from 88.9% to 72.2%. These tests lock in the
two decisions that make the fix safe rather than the fix itself.
"""

from app.retrieval.query_preprocessor import (
    detect_subject_entity,
    strip_subject_entity,
)
from app.schemas.documents import PageText


def make_pages(text: str, count: int = 10) -> list[PageText]:
    return [
        PageText(page_number=n + 1, text=text)
        for n in range(count)
    ]


# Acme appears mid-sentence throughout, so it survives the
# first-word skip; "revenue" is equally frequent but is only ever
# capitalised at a sentence start.
SUBJECT_TEXT = (
    "Revenue at Acme rose. In 2023 Acme grew. "
    "The board of Acme met. Sales at Acme were strong. "
    "Growth for Acme continued. Total revenue for Acme was high."
)


# =====================================================
# Detection
# =====================================================


def test_detects_capitalised_frequent_term():
    assert detect_subject_entity(make_pages(SUBJECT_TEXT)) == ["acme"]


def test_common_noun_of_equal_frequency_is_not_detected():
    """
    The central design decision. Document frequency alone cannot
    separate "microsoft" from "revenue" - in the real document they
    score 0.44 and 0.46. Stripping on frequency alone also removed
    "revenue", "income" and "cloud", dropping full-set recall from
    84.3% to 76.9%. Capitalisation is what distinguishes them.
    """

    entities = detect_subject_entity(make_pages(SUBJECT_TEXT))

    assert "revenue" not in entities
    assert "sales" not in entities
    assert "growth" not in entities


def test_returns_lowercase_and_sorted():
    pages = make_pages(
        "Filed by Acme Holdings. Audited for Acme Holdings. "
        "Reviewed at Acme Holdings. Signed for Acme Holdings. "
        "Issued by Acme Holdings. Held by Acme Holdings."
    )

    entities = detect_subject_entity(pages)

    assert entities == sorted(entities)
    assert all(term == term.lower() for term in entities)


def test_no_pages_returns_empty():
    assert detect_subject_entity([]) == []


def test_term_below_document_frequency_cut_is_ignored():
    """
    A proper noun confined to a minority of pages is a detail, not
    the document's subject, so it must stay in the query.
    """

    pages = make_pages(SUBJECT_TEXT, count=10)

    rare = (
        "Audited by Zenith LLP. Signed by Zenith LLP. "
        "Reviewed by Zenith LLP. Filed by Zenith LLP. "
        "Held by Zenith LLP. Noted by Zenith LLP."
    )

    pages[0] = PageText(page_number=1, text=rare)
    pages[1] = PageText(page_number=2, text=rare)

    assert "zenith" not in detect_subject_entity(pages)


def test_term_too_rare_to_judge_capitalisation_is_ignored():
    """
    Occurrences are counted across the whole document, not per page.
    Under 5 of them the capitalisation ratio is noise, so the term is
    skipped even when it clears the document-frequency cut.

    Vega here sits on 4 of 10 pages (df 0.40, above the 0.35 cut) and
    is capitalised every time, so only the rarity guard excludes it.
    """

    pages = make_pages("Filed for the year ended.", count=10)

    for n in range(4):
        pages[n] = PageText(
            page_number=n + 1,
            text="Reported by Vega today.",
        )

    assert "vega" not in detect_subject_entity(pages)


def test_ordinary_vocabulary_is_never_detected():
    pages = make_pages(
        "The results for The year. Filed with The board for The year. "
        "Noted by The board. Held for The year. Read by The board. "
        "Signed for The year and The board."
    )

    entities = detect_subject_entity(pages)

    assert "the" not in entities
    assert "year" not in entities


def test_capitalisation_cut_excludes_the_near_miss_band():
    """
    min_caps sits at 0.90 rather than 0.85 because "Total" reaches
    0.857 in the real document, capitalised in table headers. A term
    in that band must fall on the excluded side of the default cut.

    Acme appears 6 times below, capitalised in 5 of them - a ratio of
    0.833, squarely in the near-miss band.
    """

    pages = make_pages(
        "Revenue at Acme rose. Profit from Acme grew. "
        "The board of Acme met. Sales from Acme were strong. "
        "Growth for Acme continued. Filed for acme today."
    )

    assert "acme" not in detect_subject_entity(pages)
    assert "acme" in detect_subject_entity(pages, min_caps=0.80)


def test_document_frequency_cut_is_adjustable():
    pages = make_pages(SUBJECT_TEXT)

    assert detect_subject_entity(pages) == ["acme"]
    assert detect_subject_entity(pages, min_df=1.01) == []


# =====================================================
# Stripping
# =====================================================


def test_strips_entity_from_query():
    assert (
        strip_subject_entity("What was Acme revenue?", ["acme"])
        == "What was revenue?"
    )


def test_strips_possessive_form():
    assert (
        strip_subject_entity("What was Acme's revenue?", ["acme"])
        == "What was revenue?"
    )


def test_stripping_is_case_insensitive():
    assert (
        strip_subject_entity("ACME revenue for 2023", ["acme"])
        == "revenue for 2023"
    )


def test_trailing_punctuation_does_not_block_a_match():
    assert (
        strip_subject_entity("Revenue at Acme, restated", ["acme"])
        == "Revenue at restated"
    )


def test_query_without_the_entity_is_returned_unchanged():
    """
    Stripping must cost nothing on queries that never named the
    subject; full-set recall was 84.3% either way.
    """

    query = "What was total revenue in 2023?"

    assert strip_subject_entity(query, ["acme"]) == query


def test_no_entities_returns_query_unchanged():
    query = "What was Acme revenue?"

    assert strip_subject_entity(query, None) == query
    assert strip_subject_entity(query, []) == query


def test_query_made_entirely_of_entities_falls_back_to_original():
    """
    An empty query embeds to nothing useful, so the original is the
    safer fallback even though it is known to retrieve badly.
    """

    assert strip_subject_entity("Acme", ["acme"]) == "Acme"
    assert strip_subject_entity("Acme?", ["acme"]) == "Acme?"


def test_multi_word_entities_are_not_matched():
    """
    Documents a real limitation. Stripping compares one whitespace
    token at a time, and detection only ever emits single tokens, so
    a multi-word entity passed in by hand matches nothing.
    """

    query = "What was Acme Holdings revenue?"

    assert (
        strip_subject_entity(query, ["Acme Holdings"]) == query
    )
