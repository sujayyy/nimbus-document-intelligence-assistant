"""
Query preprocessing for dense retrieval.

In a single-entity corpus - one company's annual report, one product's
manual - the subject's name appears on nearly every page. It therefore
carries almost no power to discriminate between chunks, yet it still
dominates the query embedding and pulls it toward generic boilerplate
(the shareholder letter, cover matter).

Measured on the Microsoft annual report, 9 minimal pairs differing only
in "the company" vs "Microsoft":

    dense retrieval   61.1% -> 0.0% recall
    production stack  88.9% -> 72.2% recall

Cosine similarity actually RISES (0.519 -> 0.687) while accuracy
collapses: the retriever becomes more confident and less correct.

The fix is to drop the subject entity from the query before embedding
it, and only then. The CrossEncoder still scores the full original
query, because it reads question and chunk together and is far less
sensitive to this.

    query --strip subject entity--> dense retrieval
          --unchanged------------>  CrossEncoder

Stripping the entity closed the gap entirely (72.2% -> 88.9%) at no
cost to normal queries (full-set recall 84.3% either way).
"""

import re


WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z\-]{2,}\b")

# Excluded from detection so ordinary vocabulary is never treated as
# the document's subject.
COMMON = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were",
    "are", "its", "has", "have", "had", "our", "their", "which", "also",
    "not", "may", "can", "will", "would", "these", "such", "than",
    "other", "any", "all", "more", "some", "including", "under",
    "over", "into", "per", "been", "but", "who", "out", "about", "new",
    "one", "two", "three", "year", "years", "million", "billion",
}


def detect_subject_entity(
    pages,
    min_df: float = 0.35,
    min_caps: float = 0.90,
) -> list[str]:
    """
    Detect the document's subject entity: terms that are both very
    common and proper nouns.

    Document frequency alone cannot do this. In the test document
    "microsoft" and "revenue" have near-identical document frequency
    (0.44 vs 0.46), and stripping on frequency alone also removed
    "revenue", "income" and "cloud", dropping full-set recall from
    84.3% to 76.9%.

    Capitalisation separates them cleanly, because a proper noun is
    capitalised wherever it appears while a common noun is capitalised
    only at the start of a sentence:

        june 1.000 | microsoft 0.950 | total 0.857
        revenue 0.184 | income 0.196 | cloud 0.212

    "Total" is the near miss - capitalised in table headers - which is
    why the cut sits at 0.90 rather than 0.85.

    Reads original page text; chunk text comes from an uncased
    tokenizer and has already lost capitalisation.
    """

    if not pages:
        return []

    page_count = len(pages)

    doc_freq: dict[str, int] = {}
    capitalised: dict[str, int] = {}
    occurrences: dict[str, int] = {}

    for page in pages:
        seen: set[str] = set()

        for sentence in re.split(
            r"(?<=[.!?])\s+", page.text
        ):
            words = WORD_RE.findall(sentence)

            # Skip the first word: its capitalisation reflects
            # sentence position, not word class.
            for word in words[1:]:
                key = word.lower()

                occurrences[key] = (
                    occurrences.get(key, 0) + 1
                )

                if word[0].isupper():
                    capitalised[key] = (
                        capitalised.get(key, 0) + 1
                    )

                seen.add(key)

        for key in seen:
            doc_freq[key] = doc_freq.get(key, 0) + 1

    entities = []

    for term, count in doc_freq.items():

        if count / page_count < min_df:
            continue

        if term in COMMON or len(term) <= 2:
            continue

        # Too rare to judge capitalisation reliably.
        if occurrences.get(term, 0) < 5:
            continue

        ratio = (
            capitalised.get(term, 0) / occurrences[term]
        )

        if ratio >= min_caps:
            entities.append(term)

    return sorted(entities)


def strip_subject_entity(
    query: str,
    entities: list[str] | set[str] | None,
) -> str:
    """
    Remove subject-entity tokens from a query.

    Returns the query unchanged when no entities are known, or when
    stripping would empty it - an empty query embeds to nothing
    useful, so the original is always the safer fallback.
    """

    if not entities:
        return query

    terms = {e.lower() for e in entities}

    kept = [
        word
        for word in query.split()
        if word.lower().strip(".,;:?!'\"()").rstrip("'s")
        not in terms
    ]

    stripped = " ".join(kept).strip()

    return stripped if stripped else query
