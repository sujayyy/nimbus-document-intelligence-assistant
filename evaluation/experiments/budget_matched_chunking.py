"""
Token-budget-matched chunking comparison, including recursive.

Comparing chunk sizes at a fixed top_k=5 is confounded: smaller
chunks deliver less text and fewer distinct pages for the same k,
so page recall falls for reasons unrelated to embedding quality.

This holds the RETRIEVED TOKEN BUDGET approximately constant by
scaling top_k inversely with mean chunk size.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "ai-layer"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.embedder import Embedder
from app.ingestion.parser import PDFParser
from app.ingestion.chunker import TokenChunker
from app.retrieval.vector_store import FAISSVectorStore
from evaluation.experiments.retrieval_experiments import (
    ExperimentRetriever,
    Variant,
    score_case,
)

# Indexes are rebuilt per configuration; keep them out of the
# production data directory.
SCRATCH = PROJECT_ROOT / "evaluation/experiments/.indexes"
SCRATCH.mkdir(parents=True, exist_ok=True)

DOC = "b7e7f7e4-4fc9-45c1-ab4f-e817b878df3a"
PDF = (
    PROJECT_ROOT
    / "ai-layer/data/uploads"
    / f"{DOC}.pdf"
)

gold = json.loads(
    (PROJECT_ROOT / "evaluation/gold_set.json").read_text()
)
cases = gold["cases"] if isinstance(gold, dict) else gold
answerable = [c for c in cases if c["type"] != "unanswerable"]
print(f"answerable cases: {len(answerable)}", flush=True)

embedder = Embedder()
engine = ExperimentRetriever(embedder)
pages = PDFParser().parse(PDF)

BUDGET = 1900  # production: 5 chunks x ~381 mean tokens

STRATEGIES = [
    ("fixed", 256, 25),
    ("fixed", 512, 50),
    ("fixed", 1024, 100),
    ("fixed", 512, 0),
    ("fixed", 512, 102),
]

rows = []

for kind, cs, ov in STRATEGIES:
    name = f"{kind}_{cs}_{ov}"
    idx = SCRATCH / name

    chunker = TokenChunker(chunk_size=cs, chunk_overlap=ov)

    chunks = chunker.chunk_pages(pages, DOC)
    emb = embedder.embed_documents([c.text for c in chunks])

    store = FAISSVectorStore(idx)
    store.build(embeddings=emb, chunks=chunks)

    tok = embedder.model.tokenizer
    lens = [
        len(tok.encode(c.text, add_special_tokens=False))
        for c in chunks
    ]
    mean_tokens = sum(lens) / len(lens)
    limit = embedder.model.max_seq_length - 2
    dropped = sum(max(0, l - limit) for l in lens)
    drop_pct = 100 * dropped / sum(lens)

    k = max(1, round(BUDGET / mean_tokens))

    res = {}
    for vn, v in [
        ("dense", Variant("d", "Dense only", use_reranker=False, top_k=k)),
        ("ce", Variant("c", "Dense->CE", use_reranker=True, top_k=k)),
        (
            "prod",
            Variant(
                "p",
                "Production stack",
                use_reranker=True,
                use_rrf=True,
                use_financial=True,
                use_page_aware=True,
                top_k=k,
            ),
        ),
    ]:
        per = [
            score_case(
                c["primary_pages"],
                engine.rank(store, c["question"], v),
                c.get("acceptable_pages"),
            )
            for c in answerable
        ]
        n = len(per)
        res[vn] = {
            "recall": sum(x["recall"] for x in per) / n,
            "precision": sum(x["precision"] for x in per) / n,
            "mrr": sum(x["mrr"] for x in per) / n,
            "ndcg": sum(x["ndcg"] for x in per) / n,
        }

    rows.append(
        {
            "name": name,
            "kind": kind,
            "chunk_size": cs,
            "chunks": len(chunks),
            "mean_tokens": mean_tokens,
            "drop_pct": drop_pct,
            "k": k,
            "results": res,
        }
    )

print("=" * 104)
print("TOKEN-BUDGET-MATCHED CHUNKING COMPARISON (~%d tokens retrieved)" % BUDGET)
print("=" * 104)
print(
    f"{'Strategy':<20}{'N':>6}{'mean_tok':>9}{'drop%':>7}{'k':>4}  "
    f"{'Arch':<18}{'Rec':>7}{'Prec':>7}{'MRR':>7}{'nDCG':>7}"
)
print("-" * 104)
for r in rows:
    for i, (vn, s) in enumerate(r["results"].items()):
        lbl = r["name"] if i == 0 else ""
        N = str(r["chunks"]) if i == 0 else ""
        mt = f"{r['mean_tokens']:.0f}" if i == 0 else ""
        dp = f"{r['drop_pct']:.1f}" if i == 0 else ""
        kk = str(r["k"]) if i == 0 else ""
        arch = {"dense": "Dense", "ce": "Dense->CE", "prod": "Production"}[vn]
        print(
            f"{lbl:<20}{N:>6}{mt:>9}{dp:>7}{kk:>4}  {arch:<18}"
            f"{s['recall']:>6.1%}{s['precision']:>7.1%}"
            f"{s['mrr']:>7.3f}{s['ndcg']:>7.3f}"
        )
    print("-" * 104)

Path(PROJECT_ROOT / "evaluation/experiments/results/chunking_budget_matched.json").write_text(
    json.dumps(rows, indent=2)
)
