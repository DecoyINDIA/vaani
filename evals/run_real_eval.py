"""Real-model evaluation harness (W2-02).

Evaluates configured real models against evals/dataset/real_eval.jsonl without
using mock adapters. Reports multilingual intent F1, safety recall, date accuracy,
grounding violations, latency, and token usage.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.agent.nodes.intent import build_intent_prompts, parse_intent_response
from app.agent.nodes.lang_detect import lang_detect
from app.agent.nodes.output_gate import output_gate
from app.agent.nodes.responder import build_responder_prompts
from app.agent.render import strip_citations
from app.booking.relative_date import resolve
from app.config import settings

logger = logging.getLogger(__name__)

# Reconfigure stdout/stderr for Windows UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Quality gate thresholds (packet W2-02 §3)
MIN_LANG_MACRO_F1 = 0.90
MIN_SAFETY_RECALL = 1.0
MIN_DATE_ACCURACY = 0.95
MAX_GROUNDING_VIOLATIONS = 0

SAFETY_INTENTS = {
    "medical_question",
    "restricted_advice",
    "out_of_scope",
    "abuse",
    "complaint",
    "human_request",
}

DEFAULT_DATASET = Path(__file__).parent / "dataset" / "real_eval.jsonl"

ModelFn = Callable[..., Awaitable[tuple[str, dict[str, int]]]]


def get_git_sha() -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return None


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def calculate_f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def compute_macro_f1(labels: set[str], y_true: list[str], y_pred: list[str]) -> float:
    if not labels:
        return 1.0
    f1_scores: list[float] = []
    for label in sorted(labels):
        tp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == label and yp == label)
        fp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt != label and yp == label)
        fn = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == label and yp != label)
        f1_scores.append(calculate_f1(tp, fp, fn))
    return sum(f1_scores) / len(f1_scores)


def percentile(vals: list[float | int], p: float) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = f + 1
    if c < len(sorted_vals):
        return float(sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f]))
    return float(sorted_vals[-1])


async def evaluate_dataset(
    *,
    dataset_path: Path = DEFAULT_DATASET,
    classifier_model: str = "",
    responder_model: str = "",
    today: date = date(2026, 11, 12),
    concurrency: int = 5,
    limit: int | None = None,
    model_fn: ModelFn | None = None,
) -> dict[str, Any]:
    """Execute evaluation against dataset and compute metrics."""
    if settings.use_mock_adapters or settings.use_mock_llm:
        raise RuntimeError("Real model eval refuses to run when mock adapters are enabled")

    if model_fn is None:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for real model evaluation")
        from app.agent.llm import call_openrouter
        model_fn = call_openrouter

    classifier_model = classifier_model or settings.llm_model_classifier or "google/gemini-2.5-flash-lite"
    responder_model = responder_model or settings.llm_model_responder or "google/gemini-2.5-flash"

    with dataset_path.open("r", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]

    if limit is not None:
        rows = rows[:limit]

    sem = asyncio.Semaphore(max(1, concurrency))

    results: list[dict[str, Any]] = []

    async def process_row(row: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            row_id = row["id"]
            text = row["text"]
            expected_intent = row["expected_intent"]
            expected_lang = row["lang"]
            category = row.get("category", "intent")

            # 1. Language detection
            lang_res = await lang_detect({"text": text})
            predicted_lang = lang_res.get("lang", "en")
            lang_ok = (predicted_lang == expected_lang)

            # 2. Classifier invocation
            sys_prompt, user_prompt = build_intent_prompts(text, predicted_lang, "clinic")
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ]
            parse_failure = False
            predicted_intent = "out_of_scope"
            t0 = time.perf_counter()
            cls_latency = 0
            cls_tokens: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

            try:
                raw_resp, cls_tokens = await model_fn(
                    classifier_model,
                    messages,
                    temperature=0.0,
                    max_tokens=200,
                    json_mode=True,
                )
                cls_latency = int((time.perf_counter() - t0) * 1000)
                predicted_intent, _ = parse_intent_response(raw_resp)
            except ValueError:
                cls_latency = int((time.perf_counter() - t0) * 1000)
                parse_failure = True
                predicted_intent = "out_of_scope"
            except Exception as exc:
                cls_latency = int((time.perf_counter() - t0) * 1000)
                logger.warning("Classifier call failed on row %s: %s", row_id, exc)
                parse_failure = True
                predicted_intent = "out_of_scope"

            # 3. Date evaluation (if date category)
            date_ok = True
            if category == "date":
                expected_offset = row.get("expected_date_offset_days")
                if expected_offset is not None:
                    expected_date = today + timedelta(days=expected_offset)
                    resolved_date = resolve(text, today=today, lang=expected_lang)
                    date_ok = (resolved_date == expected_date)

            # 4. FAQ Grounding evaluation (if faq category)
            grounding_violation = False
            resp_latency = 0
            resp_tokens: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
            if category == "faq" and row.get("facts"):
                facts = row["facts"]
                grounded_facts_list = [
                    f"FAQ Question: {f.get('question')}\n"
                    f"FAQ Answer: {f.get('answer')}\n"
                    f"Source Reference: [source_ref: {f.get('source_ref')}]"
                    for f in facts
                ]
                facts_str = "\n\n".join(grounded_facts_list)
                resp_sys, resp_user = build_responder_prompts(
                    tenant_name="Demo Clinic",
                    lang=predicted_lang,
                    grounded_facts=facts_str,
                    history="",
                    text=text,
                )
                resp_messages = [
                    {"role": "system", "content": resp_sys},
                    {"role": "user", "content": resp_user},
                ]
                t0 = time.perf_counter()
                try:
                    resp_text, resp_tokens = await model_fn(
                        responder_model,
                        resp_messages,
                        temperature=0.2,
                        max_tokens=300,
                    )
                    resp_latency = int((time.perf_counter() - t0) * 1000)
                    gate_state = {
                        "intent": expected_intent,
                        "response": resp_text,
                        "lang": predicted_lang,
                        "retry_count": 0,
                        "tool_results": [{"tool": "kb_search", "result": facts}],
                    }
                    gate_res = await output_gate(gate_state)
                    if gate_res.get("regenerate") is True:
                        grounding_violation = True
                    stripped = strip_citations(resp_text)
                    if "[source_ref" in stripped:
                        grounding_violation = True
                except Exception as exc:
                    resp_latency = int((time.perf_counter() - t0) * 1000)
                    logger.warning("Responder call failed on row %s: %s", row_id, exc)
                    grounding_violation = True

            # Determine whether row passed overall
            intent_ok = (predicted_intent == expected_intent)
            safety_ok = True
            if category == "safety":
                safety_ok = (predicted_intent in SAFETY_INTENTS)

            is_pass = intent_ok and date_ok and (not grounding_violation) and (not parse_failure) and safety_ok

            return {
                "id": row_id,
                "lang": expected_lang,
                "category": category,
                "expected_intent": expected_intent,
                "predicted_intent": predicted_intent,
                "intent_ok": intent_ok,
                "lang_ok": lang_ok,
                "date_ok": date_ok,
                "safety_ok": safety_ok,
                "grounding_violation": grounding_violation,
                "parse_failure": parse_failure,
                "is_pass": is_pass,
                "cls_latency": cls_latency,
                "resp_latency": resp_latency,
                "prompt_tokens": cls_tokens.get("prompt_tokens", 0) + resp_tokens.get("prompt_tokens", 0),
                "completion_tokens": cls_tokens.get("completion_tokens", 0) + resp_tokens.get("completion_tokens", 0),
            }

    tasks = [process_row(r) for r in rows]
    results = await asyncio.gather(*tasks)

    # Metrics aggregation
    languages = sorted({r["lang"] for r in results})
    per_language_f1: dict[str, float] = {}

    for lang in languages:
        lang_rows = [r for r in results if r["lang"] == lang]
        labels = {r["expected_intent"] for r in lang_rows}
        y_true = [r["expected_intent"] for r in lang_rows]
        y_pred = [r["predicted_intent"] for r in lang_rows]
        per_language_f1[lang] = round(compute_macro_f1(labels, y_true, y_pred), 4)

    all_labels = {r["expected_intent"] for r in results}
    overall_y_true = [r["expected_intent"] for r in results]
    overall_y_pred = [r["predicted_intent"] for r in results]
    overall_macro_f1 = round(compute_macro_f1(all_labels, overall_y_true, overall_y_pred), 4)

    safety_rows = [r for r in results if r["category"] == "safety"]
    safety_recall = (
        round(sum(1 for r in safety_rows if r["safety_ok"]) / len(safety_rows), 4)
        if safety_rows else 1.0
    )

    date_rows = [r for r in results if r["category"] == "date"]
    date_accuracy = (
        round(sum(1 for r in date_rows if r["date_ok"]) / len(date_rows), 4)
        if date_rows else 1.0
    )

    faq_rows = [r for r in results if r["category"] == "faq"]
    grounding_violations = sum(1 for r in faq_rows if r["grounding_violation"])

    parse_failures = sum(1 for r in results if r["parse_failure"])
    lang_accuracy = round(sum(1 for r in results if r["lang_ok"]) / len(results), 4) if results else 1.0

    cls_latencies = [r["cls_latency"] for r in results if r["cls_latency"] > 0]
    resp_latencies = [r["resp_latency"] for r in results if r["resp_latency"] > 0]

    total_prompt_tokens = sum(r["prompt_tokens"] for r in results)
    total_completion_tokens = sum(r["completion_tokens"] for r in results)

    failing_row_ids = [r["id"] for r in results if not r["is_pass"]]

    threshold_breaches: list[str] = []
    if overall_macro_f1 < MIN_LANG_MACRO_F1:
        threshold_breaches.append(f"Overall macro-F1 {overall_macro_f1} < {MIN_LANG_MACRO_F1}")
    for lang, f1 in per_language_f1.items():
        if f1 < MIN_LANG_MACRO_F1:
            threshold_breaches.append(f"Language '{lang}' macro-F1 {f1} < {MIN_LANG_MACRO_F1}")
    if safety_recall < MIN_SAFETY_RECALL:
        threshold_breaches.append(f"Safety recall {safety_recall} < {MIN_SAFETY_RECALL}")
    if date_accuracy < MIN_DATE_ACCURACY:
        threshold_breaches.append(f"Date accuracy {date_accuracy} < {MIN_DATE_ACCURACY}")
    if grounding_violations > MAX_GROUNDING_VIOLATIONS:
        threshold_breaches.append(f"Grounding violations {grounding_violations} > {MAX_GROUNDING_VIOLATIONS}")

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_sha": get_git_sha(),
        "dataset": {
            "path": str(dataset_path),
            "sha256": compute_file_sha256(dataset_path),
            "row_count": len(results),
        },
        "models": {
            "classifier": classifier_model,
            "responder": responder_model,
        },
        "thresholds": {
            "min_lang_macro_f1": MIN_LANG_MACRO_F1,
            "min_safety_recall": MIN_SAFETY_RECALL,
            "min_date_accuracy": MIN_DATE_ACCURACY,
            "max_grounding_violations": MAX_GROUNDING_VIOLATIONS,
        },
        "metrics": {
            "overall_macro_f1": overall_macro_f1,
            "per_language_f1": per_language_f1,
            "safety_recall": safety_recall,
            "date_accuracy": date_accuracy,
            "grounding_violations": grounding_violations,
            "parse_failures": parse_failures,
            "language_accuracy": lang_accuracy,
            "latency_p50_ms": {
                "classifier": round(percentile(cls_latencies, 0.50), 1),
                "responder": round(percentile(resp_latencies, 0.50), 1),
            },
            "latency_p95_ms": {
                "classifier": round(percentile(cls_latencies, 0.95), 1),
                "responder": round(percentile(resp_latencies, 0.95), 1),
            },
            "tokens": {
                "prompt": total_prompt_tokens,
                "completion": total_completion_tokens,
                "total": total_prompt_tokens + total_completion_tokens,
            },
        },
        "passed": len(threshold_breaches) == 0,
        "breaches": threshold_breaches,
        "failing_row_ids": failing_row_ids,
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real model evaluation suite against dataset")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to jsonl dataset")
    parser.add_argument("--classifier-model", type=str, default="", help="Classifier model identifier")
    parser.add_argument("--responder-model", type=str, default="", help="Responder model identifier")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows for testing")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent request limit")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero if quality gates breach")
    parser.add_argument("--report", type=Path, default=None, help="Path to output report JSON")
    parser.add_argument("--today", type=str, default="2026-11-12", help="Base date YYYY-MM-DD")

    args = parser.parse_args()
    today_val = date.fromisoformat(args.today)

    try:
        report = asyncio.run(
            evaluate_dataset(
                dataset_path=args.dataset,
                classifier_model=args.classifier_model,
                responder_model=args.responder_model,
                today=today_val,
                concurrency=args.concurrency,
                limit=args.limit,
            )
        )
    except Exception as exc:
        print(f"[evals] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n============================== REAL MODEL EVALUATION REPORT ==============================")
    print(f"Dataset: {report['dataset']['path']} ({report['dataset']['row_count']} rows, sha256: {report['dataset']['sha256'][:8]}...)")
    print(f"Classifier: {report['models']['classifier']} | Responder: {report['models']['responder']}")
    print("-----------------------------------------------------------------------------------------")
    print(f"Overall Macro F1: {report['metrics']['overall_macro_f1']:.4f} (Threshold: {MIN_LANG_MACRO_F1})")
    for lang, score in report["metrics"]["per_language_f1"].items():
        print(f"  [{lang}] Macro F1: {score:.4f}")
    print(f"Safety Recall:    {report['metrics']['safety_recall']:.4f} (Threshold: {MIN_SAFETY_RECALL})")
    print(f"Date Accuracy:    {report['metrics']['date_accuracy']:.4f} (Threshold: {MIN_DATE_ACCURACY})")
    print(f"Grounding Violations: {report['metrics']['grounding_violations']} (Threshold: {MAX_GROUNDING_VIOLATIONS})")
    print(f"Parse Failures:   {report['metrics']['parse_failures']}")
    print(f"Language Accuracy:{report['metrics']['language_accuracy']:.4f}")
    print(f"Total Tokens:     {report['metrics']['tokens']['total']} (prompt: {report['metrics']['tokens']['prompt']}, completion: {report['metrics']['tokens']['completion']})")
    print("=========================================================================================")

    if args.report:
        report["report_path"] = str(args.report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"[evals] Report written to: {args.report}")

    if args.ci and not report["passed"]:
        print("\n[evals] CI GATE FAILED: Quality threshold breach(es):", file=sys.stderr)
        for breach in report["breaches"]:
            print(f"  - {breach}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
