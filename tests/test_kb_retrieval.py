from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import httpx
from app.agent.graph import build_graph
from app.config import settings
from app.kb.embedding import embed_text
from app.kb.retrieval import hybrid_search
from app.main import app
from app.models.base import get_db
from app.models.collections import KbEntries
from app.owner_api.auth import create_access_token
from app.owner_api.routes import KbUpsert, upsert_kb
from evals.run_retrieval_eval import failure_report, load_corpus
from fastapi.testclient import TestClient
from ops.reembed_kb import reembed


async def test_embedding_request_uses_configured_openrouter_contract(monkeypatch: Any) -> None:
    original_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-key"
        assert body == {
            "input": "clinic hours",
            "input_type": "search_query",
            "model": "embedding-model",
            "dimensions": 3,
            "encoding_format": "float",
        }
        return httpx.Response(200, json={"data": [{"embedding": [0, 0.5, -1]}]})

    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model_embedding", "embedding-model")
    monkeypatch.setattr(settings, "kb_embedding_dimensions", 3)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda: original_client(transport=httpx.MockTransport(handler)),
    )

    assert await embed_text("clinic hours", input_type="search_query") == [0.0, 0.5, -1.0]


def test_retrieval_corpus_has_50_versioned_multilingual_queries() -> None:
    corpus = load_corpus()
    assert len(corpus) == 10
    assert sum(len(item["queries"]) for item in corpus) == 50
    assert len({item["key"] for item in corpus}) == 10


def test_retrieval_failure_evidence_is_summary_only() -> None:
    report = failure_report(RuntimeError("secret provider response"))
    assert set(report) == {
        "adapter_mode",
        "commit",
        "corpus_sha256",
        "error",
        "passed",
    }
    assert report["error"] == "RuntimeError"
    assert "secret provider response" not in json.dumps(report)


async def test_kb_write_stores_embedding_before_reporting_success(monkeypatch: Any) -> None:
    embed = AsyncMock(return_value=[0.1, 0.2])
    monkeypatch.setattr("app.owner_api.routes.embed_text", embed)

    result = await upsert_kb(
        KbUpsert(question="  When are you open?  ", answer="  Nine to five.  "),
        "kb-write",
    )

    assert result == {"status": "success"}
    embed.assert_awaited_once_with(
        "When are you open?\nNine to five.", input_type="search_document"
    )
    document = await get_db()["kb_entries"].find_one({"tenant_id": "kb-write"})
    assert document is not None
    assert document["question"] == "When are you open?"
    assert document["embedding"] == [0.1, 0.2]
    assert document["embedding_dimensions"] == 2
    assert document["version"] == 1

    await get_db()["tenants"].insert_one({"_id": "kb-write"})
    await get_db()["users"].insert_one(
        {
            "_id": "kb-staff",
            "tenant_id": "kb-write",
            "role": "staff",
            "status": "active",
        }
    )
    token = create_access_token("kb-write", "kb-staff")
    response = TestClient(app).get(
        "/api/kb", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "embedding" not in response.json()[0]
    assert "embedding_model" not in response.json()[0]


async def test_reembedding_is_dry_run_first_and_resumable(monkeypatch: Any) -> None:
    await KbEntries("kb-reembed").insert_one(
        {"question": "Hours?", "answer": "Nine to five."}
    )
    embed = AsyncMock(return_value=[0.2, 0.3])
    monkeypatch.setattr("ops.reembed_kb.embed_text", embed)
    monkeypatch.setattr(settings, "llm_model_embedding", "approved-model")
    monkeypatch.setattr(settings, "kb_embedding_dimensions", 2)

    assert await reembed(tenant_id="kb-reembed") == {
        "mode": "dry-run",
        "candidate_count": 1,
        "limit_reached": False,
    }
    embed.assert_not_awaited()

    assert await reembed(tenant_id="kb-reembed", apply=True) == {
        "mode": "apply",
        "updated_count": 1,
        "limit_reached": False,
    }
    assert (await reembed(tenant_id="kb-reembed"))["candidate_count"] == 0


async def test_atlas_failure_falls_back_only_to_tenant_structured_key(
    monkeypatch: Any,
) -> None:
    await KbEntries("kb-a").insert_one(
        {"key": "faq_hours", "question": "Hours?", "answer": "Nine to five."}
    )
    await KbEntries("kb-a").insert_one(
        {"question": "Parking?", "answer": "Behind the clinic."}
    )
    await KbEntries("kb-b").insert_one(
        {"key": "faq_hours", "question": "Hours?", "answer": "Always open."}
    )
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "llm_model_embedding", "embedding-model")
    monkeypatch.setattr("app.kb.retrieval.embed_text", AsyncMock(return_value=[0.1]))
    monkeypatch.setattr(
        KbEntries,
        "hybrid_search",
        AsyncMock(side_effect=RuntimeError("Atlas unavailable")),
    )

    structured = await hybrid_search(
        "kb-a", "what time?", fallback_key="faq_hours"
    )
    free_text = await hybrid_search("kb-a", "parking", fallback_key=None)

    assert structured == [
        {
            "key": "faq_hours",
            "question": "Hours?",
            "answer": "Nine to five.",
            "source_ref": "faq_hours",
        }
    ]
    assert free_text == []


async def test_atlas_pipeline_filters_both_ranked_inputs_by_tenant() -> None:
    captured: list[dict[str, Any]] = []

    class EmptyCursor:
        def __aiter__(self) -> EmptyCursor:
            return self

        async def __anext__(self) -> dict[str, Any]:
            raise StopAsyncIteration

    class Collection:
        def aggregate(self, pipeline: list[dict[str, Any]]) -> EmptyCursor:
            captured.extend(pipeline)
            return EmptyCursor()

    entries = KbEntries("tenant-filter")
    entries._col = Collection()  # type: ignore[assignment]
    assert await entries.hybrid_search("hours", [0.1, 0.2], k=3) == []

    ranked = captured[0]["$rankFusion"]["input"]["pipelines"]
    assert ranked["vector"][0]["$vectorSearch"]["filter"] == {
        "tenant_id": "tenant-filter"
    }
    assert ranked["text"][0]["$search"]["compound"]["filter"] == [
        {"equals": {"path": "tenant_id", "value": "tenant-filter"}}
    ]
    assert captured[1] == {"$match": {"tenant_id": "tenant-filter"}}


async def test_missing_faq_fact_skips_responder_and_hands_off(monkeypatch: Any) -> None:
    search = AsyncMock(return_value=[])
    escalate = AsyncMock(return_value={"status": "success"})
    responder_llm = AsyncMock(side_effect=AssertionError("responder must not run"))
    monkeypatch.setattr("app.agent.nodes.tool_router.kb_search", search)
    monkeypatch.setattr("app.agent.nodes.handoff.escalate", escalate)
    monkeypatch.setattr("app.agent.nodes.responder.query_llm", responder_llm)

    result = await build_graph().ainvoke(
        {
            "tenant_id": "kb-missing",
            "conversation_id": "conversation-missing",
            "channel": "wa",
            "text": "What are your opening hours?",
        }
    )

    search.assert_awaited_once()
    escalate.assert_awaited_once()
    responder_llm.assert_not_awaited()
    assert result["escalate"] is True
    assert "our team" in result["response"]
