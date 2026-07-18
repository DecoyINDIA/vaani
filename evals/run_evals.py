"""Eval harness — the real quality gate (TRD §6, 06-engineering-plan 3.6).

Runs the labeled utterance set through the agent's classification + scope + output
paths and reports:
  - per-language intent F1 (CI gate: >=85% seed, ->90% by Week 5)
  - scope-gate accuracy
  - hallucination check (trap questions where the KB lacks the answer -> must be 0)

Usage:
    python evals/run_evals.py          # human-readable report
    python evals/run_evals.py --ci     # exit non-zero if any gate fails

Dataset: evals/dataset/utterances.jsonl
  {lang, text, expected_intent, expected_facts[]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATASET = Path(__file__).parent / "dataset" / "utterances.jsonl"
INTENT_F1_THRESHOLD = 0.85


def load_dataset() -> list[dict]:
    with DATASET.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true", help="exit non-zero on gate failure")
    args = parser.parse_args()

    cases = load_dataset()
    print(f"[evals] loaded {len(cases)} labeled utterances from {DATASET.name}")

    # TODO (Week 3, task 3.6): run cases through the graph, compute per-lang F1,
    # scope accuracy, hallucination count; fail CI below thresholds.
    raise NotImplementedError("eval scoring — 06-engineering-plan task 3.6")


if __name__ == "__main__":
    sys.exit(main())
