# Nimbus — Evaluation

Measures whether Nimbus gives a correct, verifiable answer or an honest
refusal. Page metrics are kept as diagnostics, not targets.

## Run

```bash
cd ..                    # repo root
DOC=b7e7f7e4-4fc9-45c1-ab4f-e817b878df3a

# 1. Run every gold question through the real pipeline (calls Claude)
./ai-layer/.venv/bin/python -m evaluation.run_live_evaluation $DOC

# 2. Score the results (no LLM calls, free to repeat)
./ai-layer/.venv/bin/python -m evaluation.run_evaluation
```

Step 1 writes `live_results.json`. Step 2 writes `evaluation_results.json`
and prints the scorecard.

## Files

| File | Purpose |
|---|---|
| `gold_set.json` | 24 cases — 18 answerable, 6 unanswerable |
| `run_live_evaluation.py` | runs the pipeline over the gold set |
| `run_evaluation.py` | scores the run, prints the scorecard |
| `answer_metrics.py` | answer accuracy, numeric grounding, refusal |
| `metrics.py` | page and citation metrics |
