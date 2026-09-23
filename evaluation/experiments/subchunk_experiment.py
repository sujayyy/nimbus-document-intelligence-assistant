"""
Fix the truncation defect without changing the model or chunk size.

The model-swap experiment showed a trade: a 512-window model fixes the
tail-of-chunk failures (EPS, total assets, cash) but loses ground on
narrative questions, netting out within noise. Shrinking chunks to fit
MiniLM's window also fails, because smaller chunks mean more chunks per
page, so top_k=5 covers fewer distinct pages.

This tests the standard way out of that bind - index small, return big:

    512-token parent chunk          <- what the CE and the LLM see
        |
        +-- sub-unit 1 (<=254 tok)  <- what gets embedded
        +-- sub-unit 2 (<=254 tok)

Every token reaches an embedding, while retrieval still returns whole
parent chunks, so page coverage at a given top_k is unchanged and the
generation layer keeps the context it has today.

Usage:
    python -m evaluation.subchunk_experiment <document_id>
"""

import argparse
import json
import sys
from pathlib import Path

import faiss
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_LAYER_DIR = PROJECT_ROOT / "ai-layer"
EVAL_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results"

sys.path.insert(0, str(AI_LAYER_DIR))

from app.config import settings  # noqa: E402
from app.ingestion.chunker import TokenChunker  # noqa: E402
from app.ingestion.embedder import Embedder  # noqa: E402
from app.ingestion.parser import PDFParser  # noqa: E402
from app.retrieval.vector_store import FAISSVectorStore  # noqa: E402

from evaluation.experiments.retrieval_experiments import (  # noqa: E402
    ExperimentRetriever,
    Variant,
    load_gold,
    score_case,
)


class SubChunkVectorStore:
    """
    Drop-in stand-in for FAISSVectorStore that embeds sub-units but
    returns parent chunks.

    `search` over-fetches sub-units, maps each to its parent, keeps the
    best score per parent, and returns the top_k parents - so callers
    see exactly the interface (and the chunk objects) they see today.
    """

    def __init__(self, parents, sub_embeddings, sub_to_parent):
        self.chunks = parents
        self.sub_to_parent = np.asarray(sub_to_parent)

        self.index = faiss.IndexFlatIP(
            sub_embeddings.shape[1]
        )
        self.index.add(sub_embeddings)

    def search(self, query_embedding, top_k: int):
        # Over-fetch: several sub-units can share a parent.
        fetch = min(
            self.index.ntotal,
            max(top_k * 4, top_k + 32),
        )

        scores, indices = self.index.search(
            query_embedding, fetch
        )

        best: dict[int, float] = {}

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue

            parent = int(self.sub_to_parent[idx])
            score = float(score)

            if score > best.get(parent, -1e9):
                best[parent] = score

        ranked = sorted(
            best.items(), key=lambda kv: kv[1], reverse=True
        )[:top_k]

        return [
            (self.chunks[p], s) for p, s in ranked
        ]


def split_into_subunits(
    text: str, tokenizer, max_tokens: int, overlap: int
) -> list[str]:
    ids = tokenizer.encode(text, add_special_tokens=False)

    if len(ids) <= max_tokens:
        return [text]

    step = max_tokens - overlap
    out = []

    for start in range(0, len(ids), step):
        piece = tokenizer.decode(
            ids[start : start + max_tokens],
            skip_special_tokens=True,
        ).strip()

        if piece:
            out.append(piece)

        if start + max_tokens >= len(ids):
            break

    return out


VARIANTS = [
    ("dense", Variant("d", "Dense only", use_reranker=False)),
    ("ce", Variant("c", "Dense->CE", use_reranker=True)),
    (
        "rrf",
        Variant("r", "RRF", use_reranker=True, use_rrf=True),
    ),
    (
        "prod",
        Variant(
            "p",
            "Production",
            use_reranker=True,
            use_rrf=True,
            use_financial=True,
            use_page_aware=True,
        ),
    ),
]


def evaluate(engine, store, cases, variant):
    per = []
    for case in cases:
        ranked = engine.rank(store, case["question"], variant)
        m = score_case(
            case["primary"], ranked, case["acceptable"]
        )
        m["id"] = case["id"]
        per.append(m)

    n = len(per)
    return {
        "recall": sum(c["recall"] for c in per) / n,
        "adjusted_precision": sum(
            c["adjusted_precision"] for c in per
        )
        / n,
        "mrr": sum(c["mrr"] for c in per) / n,
        "ndcg_graded": sum(c["ndcg_graded"] for c in per)
        / n,
        "cases": per,
    }


def run(document_id: str, scratch: Path):
    scratch.mkdir(parents=True, exist_ok=True)

    gold = [
        c
        for c in load_gold(EVAL_DIR / "gold_set.json")
        if c["type"] != "unanswerable"
    ]

    pages = PDFParser().parse(
        settings.uploads_dir / f"{document_id}.pdf"
    )

    embedder = Embedder()
    engine = ExperimentRetriever(embedder)
    tokenizer = embedder.model.tokenizer
    window = embedder.model.max_seq_length - 2

    # Production parent chunks, unchanged.
    parents = TokenChunker(
        chunk_size=512, chunk_overlap=50
    ).chunk_pages(pages, document_id)

    # ---- Baseline: current production index ----
    base_store = FAISSVectorStore(scratch / "baseline")
    base_store.build(
        embeddings=embedder.embed_documents(
            [c.text for c in parents]
        ),
        chunks=parents,
    )

    # ---- Sub-chunk index ----
    sub_texts, sub_to_parent = [], []

    for i, parent in enumerate(parents):
        for piece in split_into_subunits(
            parent.text, tokenizer, window, 30
        ):
            sub_texts.append(piece)
            sub_to_parent.append(i)

    sub_store = SubChunkVectorStore(
        parents=parents,
        sub_embeddings=embedder.embed_documents(sub_texts),
        sub_to_parent=sub_to_parent,
    )

    lens = [
        len(tokenizer.encode(t, add_special_tokens=False))
        for t in sub_texts
    ]
    plens = [
        len(
            tokenizer.encode(
                c.text, add_special_tokens=False
            )
        )
        for c in parents
    ]

    print(f"parent chunks : {len(parents)}")
    print(
        f"sub-units     : {len(sub_texts)} "
        f"(max {max(lens)} tokens, window {window})"
    )
    print(
        f"tokens dropped: baseline "
        f"{100 * sum(max(0, l - window) for l in plens) / sum(plens):.1f}%"
        f"  ->  sub-chunk "
        f"{100 * sum(max(0, l - window) for l in lens) / sum(lens):.1f}%"
    )

    results = {}

    for key, store in [
        ("baseline_512", base_store),
        ("subchunk", sub_store),
    ]:
        results[key] = {
            "v1": {
                v: evaluate(engine, store, gold, var)
                for v, var in VARIANTS
            },
            "v2": {
                v: evaluate(engine, store, gold, var)
                for v, var in VARIANTS
            },
        }

    for gk, glabel, n in [
        ("v2", "GOLD v2.1 (corrected)", len(gold)),
        ("v1", "GOLD v1 (original)", len(gold)),
    ]:
        print("\n" + "=" * 92)
        print(
            f"SUB-CHUNK EMBEDDING vs BASELINE - {glabel}, "
            f"{n} cases, top_k=5"
        )
        print("=" * 92)
        print(
            f"{'Index':<28}{'Arch':<14}{'Rec@5':>9}"
            f"{'AdjP@5':>9}{'MRR':>9}{'nDCGg':>9}"
        )
        print("-" * 92)

        for key, label in [
            ("baseline_512", "Baseline (38.3% dropped)"),
            ("subchunk", "Sub-chunk (0% dropped)"),
        ]:
            for i, (v, _) in enumerate(VARIANTS):
                s = results[key][gk][v]
                arch = dict(
                    dense="Dense",
                    ce="Dense->CE",
                    rrf="RRF",
                    prod="Production",
                )[v]
                print(
                    f"{(label if i == 0 else ''):<28}{arch:<14}"
                    f"{s['recall']:>8.1%}"
                    f"{s['adjusted_precision']:>9.1%}"
                    f"{s['mrr']:>9.3f}"
                    f"{s['ndcg_graded']:>9.3f}"
                )
            print("-" * 92)

    # Per-case deltas under production, v2.1
    print("\nPER-CASE CHANGE (v2.1, production):")
    b = {
        c["id"]: c
        for c in results["baseline_512"]["v2"]["prod"]["cases"]
    }
    s = {
        c["id"]: c
        for c in results["subchunk"]["v2"]["prod"]["cases"]
    }
    net = 0.0
    for i in sorted(b):
        d = s[i]["recall"] - b[i]["recall"]
        net += d
        if d:
            print(
                f"  case {i:<3} {b[i]['recall']:>4.0%} -> "
                f"{s[i]['recall']:>4.0%}  ({d:+.0%})"
            )
    print(f"  net: {net:+.2f} cases-equivalent")

    eps_b = b[5]["recall"]
    eps_s = s[5]["recall"]
    print(
        f"\nEPS probe (case 5): baseline {eps_b:.0%} -> "
        f"sub-chunk {eps_s:.0%}"
    )

    out = RESULTS_DIR / "subchunk_results.json"
    out.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("document_id")
    p.add_argument("--scratch", default="/tmp/nimbus_subchunk")
    a = p.parse_args()
    run(a.document_id, Path(a.scratch))


if __name__ == "__main__":
    main()
