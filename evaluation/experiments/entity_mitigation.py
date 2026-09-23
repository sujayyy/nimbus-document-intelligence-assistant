"""
Mitigating the entity-name effect.

Measured: adding the document's subject name to a query costs production
16.7pp of recall (dense-only loses 61.1pp; the CrossEncoder absorbs most
but not all of it).

Cause: in a single-entity corpus the subject's name appears on nearly
every page, so it carries no discriminative signal - yet it still pulls
the query embedding toward generic boilerplate.

Rather than hardcode "Microsoft", this treats it as the general case it
is: **any term occurring in most chunks is a corpus-specific stopword**.
Those terms are stripped from the query before embedding only. The
CrossEncoder still scores the full original query, because it reads the
pair jointly and is far less sensitive.

    query  --strip corpus stopwords-->  dense retrieval
           --unchanged-------------->   CrossEncoder

Usage:
    python -m evaluation.entity_mitigation <document_id>
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
from app.ingestion.parser import PDFParser  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402

from evaluation.experiments.retrieval_experiments import (  # noqa: E402
    ExperimentRetriever,
    Variant,
    load_gold,
    score_case,
)


TOKEN_RE = re.compile(r"[a-z0-9]+")

# Ordinary English stopwords are already handled by the embedder; these
# are only excluded from *reporting* so the detected list reads clearly.
COMMON = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were",
    "are", "its", "has", "have", "had", "our", "their", "which", "also",
    "not", "may", "can", "will", "would", "these", "such", "than",
    "other", "any", "all", "more", "some", "our", "including", "under",
    "over", "into", "per", "been", "but", "who", "out", "about", "new",
    "one", "two", "three", "year", "years", "million", "billion",
}


def detect_corpus_stopwords(
    chunks, threshold: float
) -> dict[str, float]:
    """
    Terms appearing in more than `threshold` of chunks.

    A term this common cannot discriminate between chunks, so including
    it in the embedded query only adds noise.

    NOTE: measured to over-strip. At the threshold that catches
    "microsoft" it also catches "revenue", "income" and "cloud", which
    are exactly what queries are about - full-set recall fell from
    84.3% to 76.9%. Kept for the record; `detect_subject_entity` is
    the discriminator that works.
    """

    n = len(chunks)
    df: dict[str, int] = {}

    for chunk in chunks:
        for term in set(TOKEN_RE.findall(chunk.text.lower())):
            df[term] = df.get(term, 0) + 1

    return {
        term: count / n
        for term, count in df.items()
        if count / n >= threshold
        and term not in COMMON
        and len(term) > 2
        and not term.isdigit()
    }


WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z\-]{2,}\b")


def detect_subject_entity(
    pages, min_df: float = 0.35, min_caps: float = 0.90
) -> dict[str, float]:
    """
    The document's subject entity: a term that is both very common and
    a proper noun.

    Document frequency alone cannot separate "microsoft" from
    "revenue" - both are everywhere. Capitalisation can: a proper noun
    is capitalised wherever it appears, while a common noun is
    capitalised only at the start of a sentence.

    This reads the ORIGINAL page text, because chunk text comes from an
    uncased tokenizer and has already lost capitalisation.

    Measured capitalisation ratios on the test document show the
    separation is clean, and why the 0.90 cut sits where it does:

        june 1.000 | microsoft 0.950 | total 0.857
        revenue 0.184 | income 0.196 | cloud 0.212

    "Total" is the near miss - capitalised in table headers but a
    common noun - so a looser 0.85 cut wrongly strips it.
    """

    n = len(pages)

    doc_freq: dict[str, int] = {}
    caps: dict[str, int] = {}
    total: dict[str, int] = {}

    for page in pages:
        seen = set()

        # Drop the first word of each sentence: its capitalisation
        # says nothing about whether it is a proper noun.
        for sentence in re.split(r"(?<=[.!?])\s+", page.text):
            words = WORD_RE.findall(sentence)

            for word in words[1:]:
                key = word.lower()
                total[key] = total.get(key, 0) + 1
                if word[0].isupper():
                    caps[key] = caps.get(key, 0) + 1
                seen.add(key)

        for key in seen:
            doc_freq[key] = doc_freq.get(key, 0) + 1

    out = {}

    for term, count in doc_freq.items():
        if count / n < min_df:
            continue
        if term in COMMON or len(term) <= 2:
            continue
        if total.get(term, 0) < 5:
            continue

        ratio = caps.get(term, 0) / total[term]

        if ratio >= min_caps:
            out[term] = count / n

    return out


def strip_terms(query: str, terms: set[str]) -> str:
    """Remove corpus-stopword tokens from a query."""

    kept = [
        word
        for word in query.split()
        if TOKEN_RE.sub(
            lambda m: m.group(0), word.lower()
        ).strip(".,?'\"s")
        not in terms
    ]

    stripped = " ".join(kept).strip()

    # Never hand the embedder an empty query.
    return stripped if stripped else query


class MitigatedEmbedder:
    """Embedder that strips corpus stopwords from queries only."""

    def __init__(self, embedder: Embedder, terms: set[str]):
        self._inner = embedder
        self.terms = terms
        self.model = embedder.model

    def embed_documents(self, texts):
        return self._inner.embed_documents(texts)

    def embed_query(self, text):
        return self._inner.embed_query(
            strip_terms(text, self.terms)
        )


ENTITY = "Microsoft"


def to_entity_form(question: str) -> str | None:
    if not re.search(r"\bthe company\b", question, re.I):
        return None
    return re.sub(
        r"\bthe company\b", ENTITY, question, flags=re.I
    )


def run(document_id: str):
    gold = load_gold(EVAL_DIR / "gold_set.json")
    answerable = [
        c for c in gold if c["type"] != "unanswerable"
    ]

    pairs = [
        (c, to_entity_form(c["question"]))
        for c in answerable
        if to_entity_form(c["question"])
    ]

    store = FAISSVectorStore(
        settings.indexes_dir / document_id
    )
    store.load()

    base = Embedder()

    production = Variant(
        "p",
        "Production",
        use_reranker=True,
        use_rrf=True,
        use_financial=True,
        use_page_aware=True,
    )

    pages = PDFParser().parse(
        settings.uploads_dir / f"{document_id}.pdf"
    )

    subject = detect_subject_entity(pages)

    print("=" * 90)
    print("ENTITY-NAME MITIGATION")
    print(f"{len(pairs)} minimal pairs + {len(answerable)} full cases")
    print("=" * 90)
    print(
        f"\nDetected subject entity (high df + proper noun): "
        f"{sorted(subject) or 'none'}"
    )

    strategies = [
        ("none (baseline)", set()),
        ("subject entity only", set(subject)),
        (
            "corpus stopwords df>=0.35",
            set(
                detect_corpus_stopwords(store.chunks, 0.35)
            ),
        ),
    ]

    results = {}

    for label, term_set in strategies:

        embedder = (
            base
            if not term_set
            else MitigatedEmbedder(base, term_set)
        )
        engine = ExperimentRetriever(embedder)

        # Robustness on the minimal pairs.
        neutral, entity = [], []
        for case, entity_q in pairs:
            neutral.append(
                score_case(
                    case["primary"],
                    engine.rank(
                        store, case["question"], production
                    ),
                    case["acceptable"],
                )["recall"]
            )
            entity.append(
                score_case(
                    case["primary"],
                    engine.rank(store, entity_q, production),
                    case["acceptable"],
                )["recall"]
            )

        # Cost on the full gold set - a fix that damages normal
        # queries is not a fix.
        full = [
            score_case(
                c["primary"],
                engine.rank(store, c["question"], production),
                c["acceptable"],
            )
            for c in answerable
        ]

        nr = sum(neutral) / len(neutral)
        er = sum(entity) / len(entity)
        fr = sum(x["recall"] for x in full) / len(full)

        results[label] = {
            "terms": sorted(term_set),
            "neutral_recall": nr,
            "entity_recall": er,
            "gap_pp": (er - nr) * 100,
            "full_recall": fr,
        }

        print(
            f"\n{label:<18} terms={len(term_set):<4} "
            f"neutral={nr:.1%}  +entity={er:.1%}  "
            f"gap={(er - nr) * 100:+.1f}pp   "
            f"full-set recall={fr:.1%}"
        )
        if term_set:
            shown = sorted(term_set)[:14]
            print(
                f"{'':<18} stripped: {', '.join(shown)}"
                f"{' ...' if len(term_set) > 14 else ''}"
            )

    print("\n" + "=" * 90)

    out = RESULTS_DIR / "entity_mitigation_results.json"
    out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("document_id")
    run(p.parse_args().document_id)


if __name__ == "__main__":
    main()
