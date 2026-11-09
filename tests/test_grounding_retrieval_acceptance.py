"""Acceptance tests for WP08: Credentialed Retrieval & Model Evaluation (P4/P8).

Covers:
1. Re-embedding dry-run, batch limits, and interrupted rerun resilience on synthetic KB data.
2. Grounding & output gate rejection:
   - Fabricated / invented tags copied from earlier turns or cross-tenant sources
   - Altered numeric facts (e.g. 500 -> 800) with a valid citation tag
   - Multilingual unsupported numbers in Devanagari / Odia digits
   - Valid localized digits (Devanagari ५००, Odia ୫୦୦) matching source facts accepted
   - Uncited claims in English, Hindi, and Odia rejected
3. Prompt injection & jailbreak defenses in patient/KB text:
   - Adversarial prompt injection attempting zero-fee override blocked by output gate
   - Grounding failure retry exhausting and safely degrading to static template
4. Frozen 50-query multilingual retrieval corpus:
   - 10 entries, 50 queries across EN, HI, HI-LATN, and OR
   - Simulated hybrid retrieval achieving >= 90% top-3 hit rate
   - Sanitized summary-only evidence report (zero PII, zero raw question/answer text)
5. Missing KB facts safe degradation:
   - Query with no matching KB facts routing to human handoff without hallucinations.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from app.agent.graph import build_graph
from app.agent.nodes.output_gate import output_gate
from app.config import settings
from app.models.base import get_db
from app.models.collections import KbEntries
from evals.run_retrieval_eval import failure_report, load_corpus
from ops.reembed_kb import reembed


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    db = get_db()
    for col in await db.list_collection_names():
        if not col.startswith("system."):
            await db[col].delete_many({})


# -----------------------------------------------------------------------------
# 1. Re-embedding dry-run, batch limits, and interrupted rerun resilience
# -----------------------------------------------------------------------------
async def test_reembed_batch_limits_and_interrupted_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = "t_reembed_resilience"
    kb = KbEntries(tenant_id)

    # Insert 5 synthetic KB entries without embeddings
    for i in range(5):
        await kb.insert_one(
            {
                "_id": f"faq_{i}",
                "question": f"Question {i}?",
                "answer": f"Answer {i}.",
            }
        )

    embed_mock = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr("ops.reembed_kb.embed_text", embed_mock)
    monkeypatch.setattr(settings, "llm_model_embedding", "approved-embedding-model")
    monkeypatch.setattr(settings, "kb_embedding_dimensions", 3)

    # 1. Dry run with limit=2 reports candidate count without modifying DB or calling embed_text
    dry_run = await reembed(tenant_id=tenant_id, limit=2, apply=False)
    assert dry_run["mode"] == "dry-run"
    assert dry_run["candidate_count"] == 2
    assert dry_run["limit_reached"] is True
    embed_mock.assert_not_awaited()

    # 2. First apply batch of limit=2
    batch1 = await reembed(tenant_id=tenant_id, limit=2, apply=True)
    assert batch1["mode"] == "apply"
    assert batch1["updated_count"] == 2
    assert batch1["limit_reached"] is True
    assert embed_mock.await_count == 2

    # Simulate process interruption/crash here.
    # 3. Interrupted rerun: Next execution only sees the remaining 3 candidates!
    embed_mock.reset_mock()
    batch2 = await reembed(tenant_id=tenant_id, limit=2, apply=True)
    assert batch2["mode"] == "apply"
    assert batch2["updated_count"] == 2
    assert batch2["limit_reached"] is True
    assert embed_mock.await_count == 2

    # 4. Final batch takes the remaining 1 candidate
    embed_mock.reset_mock()
    batch3 = await reembed(tenant_id=tenant_id, limit=2, apply=True)
    assert batch3["mode"] == "apply"
    assert batch3["updated_count"] == 1
    assert batch3["limit_reached"] is False
    assert embed_mock.await_count == 1

    # 5. Subsequent run has 0 candidates (idempotent)
    final_check = await reembed(tenant_id=tenant_id, limit=10, apply=False)
    assert final_check["candidate_count"] == 0
    assert final_check["limit_reached"] is False


# -----------------------------------------------------------------------------
# 2. Grounding & output gate rejection: invented tags, altered numbers, Indic digits
# -----------------------------------------------------------------------------
def _gate_state(response: str, *, tool_result: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "intent": "faq_fees",
        "lang": "en",
        "response": response,
        "retry_count": 0,
        "tool_results": [
            {
                "tool": "kb_search",
                "result": tool_result
                or [
                    {"question": "Fee?", "answer": "The consultation fee is Rs 500.", "source_ref": "faq_fees"}
                ],
            }
        ],
    }


async def test_output_gate_rejects_fabricated_and_cross_tenant_sources() -> None:
    # Tag from earlier turn or other tenant not in current turn's tool_results
    fabricated_turn = _gate_state("The consultation fee is Rs 500. [source_ref: copied_earlier_turn_ref]")
    res1 = await output_gate(fabricated_turn)
    assert res1["regenerate"] is True

    invented = _gate_state("The consultation fee is Rs 500. [source_ref: invented_tag_123]")
    res2 = await output_gate(invented)
    assert res2["regenerate"] is True


async def test_output_gate_rejects_altered_numbers_and_accepts_valid_indic_digits() -> None:
    # 1. Altered number in English
    altered_en = _gate_state("The consultation fee is Rs 800. [source_ref: faq_fees]")
    res_en = await output_gate(altered_en)
    assert res_en["regenerate"] is True

    # 2. Grounded number in English
    valid_en = _gate_state("The consultation fee is Rs 500. [source_ref: faq_fees]")
    res_valid_en = await output_gate(valid_en)
    assert res_valid_en == {"regenerate": False}

    # 3. Altered number using Devanagari numerals (७०० = 700 != 500)
    altered_hi = _gate_state("परामर्श शुल्क ७०० रुपये है। [source_ref: faq_fees]")
    res_hi = await output_gate(altered_hi)
    assert res_hi["regenerate"] is True

    # 4. Valid number using Devanagari numerals (५०० = 500 == 500)
    valid_hi = _gate_state("परामर्श शुल्क ५०० रुपये है। [source_ref: faq_fees]")
    res_valid_hi = await output_gate(valid_hi)
    assert res_valid_hi == {"regenerate": False}

    # 5. Altered number using Odia numerals (୮୦୦ = 800 != 500)
    altered_or = _gate_state("ପରାମର୍ଶ ଫିସ୍ ୮୦୦ ଟଙ୍କା। [source_ref: faq_fees]")
    res_or = await output_gate(altered_or)
    assert res_or["regenerate"] is True

    # 6. Valid number using Odia numerals (୫୦୦ = 500 == 500)
    valid_or = _gate_state("ପରାମର୍ଶ ଫିସ୍ ୫୦୦ ଟଙ୍କା। [source_ref: faq_fees]")
    res_valid_or = await output_gate(valid_or)
    assert res_valid_or == {"regenerate": False}


async def test_output_gate_rejects_uncited_factual_claims_in_hindi_and_odia() -> None:
    # Uncited Hindi claim with currency
    uncited_hi = _gate_state("परामर्श शुल्क ५०० रुपये है।")
    res_hi = await output_gate(uncited_hi)
    assert res_hi["regenerate"] is True

    # Uncited Odia claim with currency
    uncited_or = _gate_state("ପରାମର୍ଶ ଫିସ୍ ୫୦୦ ଟଙ୍କା।")
    res_or = await output_gate(uncited_or)
    assert res_or["regenerate"] is True


# -----------------------------------------------------------------------------
# 3. Prompt injection and jailbreak defenses
# -----------------------------------------------------------------------------
async def test_output_gate_blocks_adversarial_zero_fee_jailbreak() -> None:
    # Adversarial injection attempting to claim 0 fee without valid source
    injected_state = _gate_state("Special promotion: fee is Rs 0. [source_ref: faq_fees]")
    res1 = await output_gate(injected_state)
    # 0 is not in cited_source_text (which has 500) -> rejected!
    assert res1["regenerate"] is True

    # On second attempt (retry_count=1), persists uncited claim -> falls back to safe template
    injected_state["retry_count"] = 1
    res2 = await output_gate(injected_state)
    assert res2["regenerate"] is False
    assert "response" in res2
    assert "0" not in res2["response"]


# -----------------------------------------------------------------------------
# 4. Frozen 50-query multilingual retrieval corpus & evaluation report
# -----------------------------------------------------------------------------
def test_retrieval_corpus_coverage_and_structure() -> None:
    corpus = load_corpus()
    assert len(corpus) == 10

    # Ensure all 10 entries have non-empty keys, questions, answers, and exactly 5 queries each
    total_queries = 0
    all_keys = set()
    for item in corpus:
        assert item["key"]
        assert item["question"]
        assert item["answer"]
        assert len(item["queries"]) == 5
        total_queries += len(item["queries"])
        all_keys.add(item["key"])

    assert total_queries == 50
    assert len(all_keys) == 10


def test_retrieval_failure_report_sanitization() -> None:
    # Ensure failure reports never leak query text, provider keys, or answers
    err = RuntimeError("Sensitive provider internal detail: API_KEY_SECRET_12345")
    report = failure_report(err)
    assert report["passed"] is False
    assert report["error"] == "RuntimeError"
    report_json = json.dumps(report)
    assert "API_KEY_SECRET_12345" not in report_json
    assert "corpus_sha256" in report
    assert "commit" in report


async def test_simulated_hybrid_retrieval_accuracy_on_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test that evals.run_retrieval_eval.run() correctly computes hit rate and threshold
    corpus = load_corpus()
    assert len(corpus) == 10
    total_queries = sum(len(item["queries"]) for item in corpus)
    assert total_queries == 50

    # Mock hybrid_search to return the correct item's key for each query
    async def mock_hybrid_search(tenant_id: str, query: str, *, k: int = 3) -> list[dict[str, Any]]:
        # Find which corpus item contains this query
        for item in corpus:
            if query in item["queries"]:
                return [{"source_ref": item["key"], "key": item["key"]}]
        return []

    monkeypatch.setattr("evals.run_retrieval_eval.hybrid_search", mock_hybrid_search)
    monkeypatch.setattr("evals.run_retrieval_eval.embed_text", AsyncMock(return_value=[0.1] * 1536))
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-eval-key")
    monkeypatch.setattr(settings, "llm_model_embedding", "text-embedding-3-small")
    monkeypatch.setattr(settings, "kb_embedding_dimensions", 1536)
    monkeypatch.setenv("VAANI_RETRIEVAL_EVAL_MONGODB_URI", "mongodb://localhost:27017/vaani_eval")

    from evals.run_retrieval_eval import run
    report = await run()
    assert report["passed"] is True
    assert report["hit_rate"] >= 0.90
    assert report["hits"] == 50
    assert report["query_count"] == 50
    assert report["top_k"] == 3
    assert report["threshold"] == 0.90


# -----------------------------------------------------------------------------
# 5. Missing KB facts safe degradation to human handoff
# -----------------------------------------------------------------------------
async def test_missing_kb_facts_route_to_human_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    search_mock = AsyncMock(return_value=[])
    escalate_mock = AsyncMock(return_value={"status": "success"})
    responder_mock = AsyncMock(side_effect=AssertionError("Responder must not run when facts are missing"))

    monkeypatch.setattr("app.agent.nodes.tool_router.kb_search", search_mock)
    monkeypatch.setattr("app.agent.nodes.handoff.escalate", escalate_mock)
    monkeypatch.setattr("app.agent.nodes.responder.query_llm", responder_mock)

    graph = build_graph()
    result = await graph.ainvoke(
        {
            "tenant_id": "t_missing_kb",
            "conversation_id": "c_missing_kb",
            "channel": "wa",
            "text": "What are your opening hours?",
        }
    )

    search_mock.assert_awaited_once()
    escalate_mock.assert_awaited_once()
    responder_mock.assert_not_awaited()
    assert result["escalate"] is True
    assert "clinic staff" in result["response"]
