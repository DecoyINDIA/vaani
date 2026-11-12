"""Tests for hardened LLM client, retries, fallback, JSON mode, and telemetry (W2-04)."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from app.agent.llm import LlmError, query_llm, set_http_client
from app.config import settings
from app.models.base import get_db
from app.models.collections import LlmCalls


@pytest.fixture(autouse=True)
def reset_llm_client() -> Generator[None, None, None]:
    set_http_client(None)
    yield
    set_http_client(None)


@pytest.fixture(autouse=True)
async def clean_llm_calls_db() -> None:
    db = get_db()
    await db["llm_calls"].delete_many({})


@pytest.mark.asyncio
async def test_llm_client_success_returns_text_and_records_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")

    tenant_id = "tenant-llm-1"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "primary-model"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello from OpenRouter"}}],
                "usage": {"prompt_tokens": 15, "completion_tokens": 25},
            },
        )

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    res = await query_llm(
        "hello",
        "primary-model",
        node="intent",
        tenant_id=tenant_id,
    )
    assert res == "Hello from OpenRouter"

    # Verify telemetry in datastore
    calls = [c async for c in LlmCalls(tenant_id).find({})]
    assert len(calls) == 1
    call = calls[0]
    assert call["tenant_id"] == tenant_id
    assert call["node"] == "intent"
    assert call["model"] == "primary-model"
    assert call["ok"] is True
    assert call["prompt_tokens"] == 15
    assert call["completion_tokens"] == 25
    assert call["error_type"] is None
    assert isinstance(call["latency_ms"], int)


@pytest.mark.asyncio
async def test_llm_client_retryable_timeout_falls_back_to_secondary_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    monkeypatch.setattr(settings, "llm_model_fallback_provider", "fallback-model")

    tenant_id = "tenant-llm-retry"
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        attempts.append(model)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Fallback response"}}],
                "usage": {"prompt_tokens": 8, "completion_tokens": 12},
            },
        )

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    res = await query_llm(
        "hello",
        "primary-model",
        node="responder",
        tenant_id=tenant_id,
    )
    assert res == "Fallback response"
    assert attempts == ["primary-model", "fallback-model"]

    # Verify two telemetry entries: 1 failure, 1 success
    calls = [c async for c in LlmCalls(tenant_id).find({})]
    assert len(calls) == 2
    assert calls[0]["ok"] is False
    assert calls[0]["model"] == "primary-model"
    assert calls[0]["error_type"] == "LlmTimeoutError"
    assert calls[1]["ok"] is True
    assert calls[1]["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_llm_client_http_400_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")

    tenant_id = "tenant-llm-400"
    calls_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls_count
        calls_count += 1
        return httpx.Response(400, text="Bad Request: invalid parameter")

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(LlmError) as exc_info:
        await query_llm(
            "hello",
            "primary-model",
            node="intent",
            tenant_id=tenant_id,
        )
    assert exc_info.value.retryable is False
    assert calls_count == 1

    calls = [c async for c in LlmCalls(tenant_id).find({})]
    assert len(calls) == 1
    assert calls[0]["ok"] is False
    assert calls[0]["error_type"] == "LlmError"


@pytest.mark.asyncio
async def test_llm_client_http_500_retries_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    monkeypatch.setattr(settings, "llm_model_fallback_provider", "fallback-model")

    tenant_id = "tenant-llm-500"
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        attempts.append(body["model"])
        return httpx.Response(500, text="Internal Server Error")

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(RuntimeError, match="OpenRouter query failed after fallback retry"):
        await query_llm(
            "hello",
            "primary-model",
            node="intent",
            tenant_id=tenant_id,
        )
    assert attempts == ["primary-model", "fallback-model"]

    calls = [c async for c in LlmCalls(tenant_id).find({})]
    assert len(calls) == 2
    assert calls[0]["ok"] is False
    assert calls[1]["ok"] is False


@pytest.mark.asyncio
async def test_llm_client_json_mode_adds_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", False)
    monkeypatch.setattr(settings, "use_mock_llm", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    monkeypatch.setattr(settings, "llm_json_mode", True)

    captured_payload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"intent": "book"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        )

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    res = await query_llm(
        "book tomorrow",
        "primary-model",
        json_mode=True,
        node="intent",
        tenant_id="t-json",
    )
    assert res == '{"intent": "book"}'
    assert captured_payload.get("response_format") == {"type": "json_object"}


@pytest.mark.asyncio
async def test_llm_client_mock_mode_makes_no_http_call_and_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "use_mock_adapters", True)
    monkeypatch.setattr(settings, "use_mock_llm", False)

    transport_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transport_called
        transport_called = True
        return httpx.Response(200, json={})

    set_http_client(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    res = await query_llm(
        "hello",
        "primary-model",
        system_prompt="You are an intent classifier",
        node="intent",
        tenant_id="tenant-mock",
    )
    assert "intent" in res
    assert transport_called is False

    calls = [c async for c in LlmCalls("tenant-mock").find({})]
    assert len(calls) == 0
