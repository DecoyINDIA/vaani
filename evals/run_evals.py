"""Eval harness — the real quality gate (TRD §6, 06-engineering-plan 3.6).

Runs the labeled utterance set through the agent's classification + scope + output
paths and reports F1 scores and checks for hallucinations.

Usage:
    python evals/run_evals.py          # human-readable report
    python evals/run_evals.py --ci     # exit non-zero if any gate fails
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from collections import defaultdict

# Reconfigure stdout/stderr to UTF-8 for Windows compatibility with Indic scripts
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.config import settings
from app.agent.graph import build_graph

DATASET = Path(__file__).parent / "dataset" / "utterances.jsonl"
INTENT_F1_THRESHOLD = 0.85


def load_dataset() -> list[dict]:
    with DATASET.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def calculate_f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    return 2 * (precision * recall) / (precision + recall)


async def run_evaluation(classifier_model: str | None, responder_model: str | None) -> dict:
    # Seed the mock database first so that in-memory query tests have clinic data
    from ops.seed_tenant import seed_async
    await seed_async("default.yaml")

    # Apply model overrides
    if classifier_model:
        settings.llm_model_classifier = classifier_model
    if responder_model:
        settings.llm_model_responder = responder_model

    cases = load_dataset()
    app = build_graph()

    results = []
    
    # Store TP, FP, FN counts per intent to calculate F1 segmented by language
    lang_stats = defaultdict(lambda: {
        "tp": defaultdict(int),
        "fp": defaultdict(int),
        "fn": defaultdict(int),
        "total": 0,
        "correct": 0
    })

    print(f"\n[evals] Running {len(cases)} evaluation cases...")
    print(f"[evals] Classifier model: {settings.llm_model_classifier or 'default (mock/fallback)'}")
    print(f"[evals] Responder model: {settings.llm_model_responder or 'default (mock/fallback)'}")
    print("-" * 80)

    for idx, case in enumerate(cases):
        lang = case["lang"]
        text = case["text"]
        expected_intent = case["expected_intent"]
        
        # Invoke agent graph
        state = {
            "tenant_id": "test_tenant",
            "conversation_id": f"eval_conv_{idx}",
            "channel": "wa",
            "text": text
        }
        
        try:
            res = await app.ainvoke(state)
            actual_intent = res.get("intent", "out_of_scope")
            response = res.get("response", "")
        except Exception as e:
            print(f"[evals] ERROR on case '{text}': {e}")
            actual_intent = "error"
            response = ""

        # Update stats
        lang_stats[lang]["total"] += 1
        
        # Record classification outcomes for intent
        if actual_intent == expected_intent:
            lang_stats[lang]["correct"] += 1
            lang_stats[lang]["tp"][expected_intent] += 1
        else:
            lang_stats[lang]["fp"][actual_intent] += 1
            lang_stats[lang]["fn"][expected_intent] += 1

        # Check for hallucination/grounding
        hallucinated = False
        if expected_intent == "medical_question" and "appointment" not in response.lower() and "consult" not in response.lower() and "ସିଧାସଳଖ" not in response:
            hallucinated = True
            
        print(f"[{lang.upper()}] Input: '{text}'")
        print(f"       Expected: {expected_intent} | Actual: {actual_intent}")
        print(f"       Response: {response[:100]}...")
        print("-" * 80)
        
        results.append({
            "case": case,
            "actual_intent": actual_intent,
            "response": response,
            "hallucinated": hallucinated
        })

    # Compute F1 scores
    print("\n" + "=" * 40 + " EVALUATION REPORT " + "=" * 40)
    
    ci_pass = True
    
    for lang, stats in lang_stats.items():
        # Calculate Macro F1
        intents_evaluated = set(list(stats["tp"].keys()) + list(stats["fp"].keys()) + list(stats["fn"].keys()))
        f1_scores = []
        for intent_name in intents_evaluated:
            tp = stats["tp"][intent_name]
            fp = stats["fp"][intent_name]
            fn = stats["fn"][intent_name]
            f1 = calculate_f1(tp, fp, fn)
            f1_scores.append(f1)
            
        macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        
        print(f"Language: {lang.upper()}")
        print(f"  Accuracy: {accuracy * 100:.2f}% ({stats['correct']}/{stats['total']})")
        print(f"  Macro F1: {macro_f1:.4f} (Threshold: {INTENT_F1_THRESHOLD})")
        
        if macro_f1 < INTENT_F1_THRESHOLD:
            print(f"  [FAIL] Macro F1 below threshold!")
            ci_pass = False
        else:
            print(f"  [PASS] Macro F1 meets threshold.")

    hallucinations = [r for r in results if r["hallucinated"]]
    print(f"\nHallucination Incidents: {len(hallucinations)}")
    if len(hallucinations) > 0:
        print("  [FAIL] Hallucination incidents found!")
        ci_pass = False
        for h in hallucinations:
            print(f"    Text: '{h['case']['text']}' | Response: '{h['response']}'")
    else:
        print("  [PASS] Zero hallucination incidents.")

    print("=" * 99)
    return {"pass": ci_pass, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true", help="exit non-zero on gate failure")
    parser.add_argument("--classifier-model", type=str, default=None, help="override intent classifier model")
    parser.add_argument("--responder-model", type=str, default=None, help="override responder model")
    args = parser.parse_args()

    # Run the evaluation loop
    res = asyncio.run(run_evaluation(args.classifier_model, args.responder_model))
    
    if args.ci and not res["pass"]:
        print("[evals] CI Gate Failed!")
        return 1
        
    print("[evals] Evaluation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
