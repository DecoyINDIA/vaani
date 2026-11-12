"""Tests for the real-model evaluation harness and dataset (W2-02)."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date
from typing import Any

import pytest
from app.agent.nodes.intent import TAXONOMY
from app.config import settings
from evals.run_real_eval import (
    DEFAULT_DATASET,
    evaluate_dataset,
)


@pytest.fixture(autouse=True)
def ensure_mock_mode_off(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    yield


def test_dataset_schema_and_minimum_counts() -> None:
    """Validate dataset structure, required fields, taxonomy, and distribution."""
    assert DEFAULT_DATASET.exists(), f"Dataset file {DEFAULT_DATASET} must exist"

    with DEFAULT_DATASET.open("r", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]

    # 1. Total rows >= 300
    assert len(rows) >= 300, f"Expected >= 300 rows, got {len(rows)}"

    lang_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    seen_ids: set[str] = set()

    for r in rows:
        # Schema checks
        assert "id" in r
        assert "lang" in r
        assert "text" in r
        assert "expected_intent" in r
        assert "category" in r
        assert "expected_date_offset_days" in r
        assert "facts" in r
        assert "reviewed" in r
        assert r["reviewed"] is False

        # Unique IDs
        assert r["id"] not in seen_ids, f"Duplicate id: {r['id']}"
        seen_ids.add(r["id"])

        # Intent in closed taxonomy
        assert r["expected_intent"] in TAXONOMY, f"Unknown intent: {r['expected_intent']}"

        # Category checks
        cat = r["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
        lang = r["lang"]
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

        if cat == "date":
            assert isinstance(r["expected_date_offset_days"], int)
        if cat == "faq":
            assert isinstance(r["facts"], list)
            assert len(r["facts"]) > 0
            for fact in r["facts"]:
                assert "source_ref" in fact
                assert "question" in fact
                assert "answer" in fact
                # Answer must carry a number
                assert any(c.isdigit() for c in fact["answer"])

    # 2. >= 60 per language
    for expected_lang in ("en", "hi", "hi-Latn", "or"):
        count = lang_counts.get(expected_lang, 0)
        assert count >= 60, f"Expected >= 60 rows for {expected_lang}, got {count}"

    # 3. Category minimums
    assert category_counts.get("safety", 0) >= 40, f"Expected >= 40 safety rows, got {category_counts.get('safety')}"
    assert category_counts.get("date", 0) >= 40, f"Expected >= 40 date rows, got {category_counts.get('date')}"
    assert category_counts.get("faq", 0) >= 60, f"Expected >= 60 faq rows, got {category_counts.get('faq')}"


@pytest.mark.asyncio
async def test_harness_refuses_to_start_in_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real evaluation harness must fail fast if mock adapters are enabled."""
    monkeypatch.setattr(settings, "use_mock_adapters", True)

    async def fake_model(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, int]]:
        return '{"intent": "greet", "confidence": 1.0}', {"prompt_tokens": 10, "completion_tokens": 10}

    with pytest.raises(RuntimeError, match="refuses to run when mock adapters are enabled"):
        await evaluate_dataset(model_fn=fake_model, limit=5)


@pytest.mark.asyncio
async def test_perfect_fake_model_passes_all_gates() -> None:
    """A perfect model function must satisfy all metrics and produce a passing report."""
    with DEFAULT_DATASET.open("r", encoding="utf-8") as fh:
        dataset_rows = {r["id"]: r for r in (json.loads(line) for line in fh if line.strip())}

    async def perfect_model(
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, int]]:
        user_msg = messages[-1]["content"]
        # Extract user message text
        import re
        m = re.search(r"User message: '(.*)'", user_msg)
        text = m.group(1) if m else user_msg

        if json_mode:
            # Find row by matching text
            matched_intent = "out_of_scope"
            for row in dataset_rows.values():
                if row["text"] == text:
                    matched_intent = row["expected_intent"]
                    break
            payload = json.dumps({"intent": matched_intent, "confidence": 0.99})
            return payload, {"prompt_tokens": 20, "completion_tokens": 10}

        # Responder path (echo grounded facts with citation)
        system_msg = messages[0]["content"]
        ref_match = re.search(r"Source Reference: \[source_ref:\s*([^\]]+)\]", system_msg)
        ref = ref_match.group(1) if ref_match else "faq_fees"
        ans_match = re.search(r"FAQ Answer: (.*)", system_msg)
        ans = ans_match.group(1) if ans_match else "The fee is Rs 500."
        return f"{ans} [source_ref: {ref}]", {"prompt_tokens": 40, "completion_tokens": 20}

    report = await evaluate_dataset(
        model_fn=perfect_model,
        today=date(2026, 11, 12),
        concurrency=10,
    )

    assert report["passed"] is True
    assert report["breaches"] == []
    assert report["breaches"] == []
    assert report["metrics"]["overall_macro_f1"] == 1.0
    for lang, f1 in report["metrics"]["per_language_f1"].items():
        assert f1 == 1.0, f"Expected 1.0 for {lang}, got {f1}"
    assert report["metrics"]["safety_recall"] == 1.0
    assert report["metrics"]["date_accuracy"] >= 0.95
    assert report["metrics"]["grounding_violations"] == 0
    assert report["metrics"]["parse_failures"] == 0
    assert report["failing_row_ids"] == []


@pytest.mark.asyncio
async def test_fake_mislabeling_odia_fails_per_language_gate() -> None:
    """Mislabelling one language must fail the per-language quality gate."""
    with DEFAULT_DATASET.open("r", encoding="utf-8") as fh:
        dataset_rows = {r["id"]: r for r in (json.loads(line) for line in fh if line.strip())}

    async def odia_failing_model(
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, int]]:
        user_msg = messages[-1]["content"]
        import re
        m = re.search(r"User message: '(.*)'", user_msg)
        text = m.group(1) if m else user_msg

        if json_mode:
            matched_row = None
            for row in dataset_rows.values():
                if row["text"] == text:
                    matched_row = row
                    break

            # Deliberately misclassify all Odia rows as out_of_scope
            if matched_row and matched_row["lang"] == "or":
                return json.dumps({"intent": "out_of_scope", "confidence": 0.99}), {"prompt_tokens": 10, "completion_tokens": 10}

            exp = matched_row["expected_intent"] if matched_row else "out_of_scope"
            return json.dumps({"intent": exp, "confidence": 0.99}), {"prompt_tokens": 10, "completion_tokens": 10}

        return "Answer [source_ref: faq_fees]", {"prompt_tokens": 10, "completion_tokens": 10}

    report = await evaluate_dataset(
        model_fn=odia_failing_model,
        today=date(2026, 11, 12),
        concurrency=10,
    )

    assert report["passed"] is False
    assert report["metrics"]["per_language_f1"]["or"] < 0.90
    assert any("Language 'or' macro-F1" in b for b in report["breaches"])


@pytest.mark.asyncio
async def test_fake_responder_with_unsupported_number_yields_grounding_violation() -> None:
    """Hallucinating numbers outside grounded facts triggers grounding violations."""
    async def hallucinating_model(
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, int]]:
        if json_mode:
            return json.dumps({"intent": "faq_fees", "confidence": 0.99}), {"prompt_tokens": 10, "completion_tokens": 10}
        # Injects an unsupported number "99999" into the response
        return "The special fee is Rs 99999. [source_ref: faq_fees]", {"prompt_tokens": 20, "completion_tokens": 20}

    report = await evaluate_dataset(
        model_fn=hallucinating_model,
        today=date(2026, 11, 12),
        limit=40,
    )

    assert report["metrics"]["grounding_violations"] > 0
    assert report["passed"] is False
    assert any("Grounding violations" in b for b in report["breaches"])


@pytest.mark.asyncio
async def test_report_contains_ids_but_no_utterance_text() -> None:
    """The JSON report must not leak patient utterance text."""
    with DEFAULT_DATASET.open("r", encoding="utf-8") as fh:
        sample_rows = [json.loads(line) for line in fh if line.strip()][:10]

    async def simple_model(*_args: Any, **_kwargs: Any) -> tuple[str, dict[str, int]]:
        return '{"intent": "greet", "confidence": 1.0}', {"prompt_tokens": 10, "completion_tokens": 10}

    report = await evaluate_dataset(
        model_fn=simple_model,
        limit=10,
    )

    report_str = json.dumps(report)
    for row in sample_rows:
        assert row["text"] not in report_str, f"Utterance text '{row['text']}' leaked in report"
    # Row IDs should be present in failing_row_ids
    assert all(isinstance(rid, str) for rid in report["failing_row_ids"])
