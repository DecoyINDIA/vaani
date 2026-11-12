"""Tests verifying no hardcoded clinic identity or prohibited literals in app/agent (W1-02)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from app.agent.nodes.responder import responder
from app.agent.state import AgentState
from app.agent.tenant_context import get_tenant_profile
from app.models.base import get_db

PROHIBITED_LITERALS = [
    "sharma",
    "dental",
    "dentist",
    "bhubaneswar",
    "दंत",
    "ଦନ୍ତ",
]


def test_no_hardcoded_tenant_literals_in_agent_code() -> None:
    agent_dir = Path("app/agent")
    pattern = re.compile("|".join(re.escape(w) for w in PROHIBITED_LITERALS), re.IGNORECASE)

    violations: list[str] = []
    for path in agent_dir.rglob("*.py"):
        if path.name == "llm.py":
            continue
        content = path.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        if matches:
            violations.append(f"{path.as_posix()}: found {matches}")

    assert not violations, "Prohibited tenant literals found in app/agent:\n" + "\n".join(violations)


async def test_responder_system_prompt_uses_tenant_name_and_no_intent_or_classify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = "test-tenant-identity"
    tenant_name = "Apex Health Centre"
    await get_db()["tenants"].insert_one({
        "_id": tenant_id,
        "name": tenant_name,
        "timezone": "Asia/Kolkata",
    })

    captured_prompts: list[dict[str, Any]] = []

    async def mock_query_llm(
        prompt: str,
        model: str = "",
        system_prompt: str = "",
        **kwargs: Any,
    ) -> str:
        captured_prompts.append({
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": prompt,
        })
        return "Namaste! How can I help you today? [source_ref: fallback]"

    import app.agent.nodes.responder as responder_mod

    monkeypatch.setattr(responder_mod, "query_llm", mock_query_llm)

    state: AgentState = {
        "tenant_id": tenant_id,
        "conversation_id": "conv-tenant-test",
        "text": "hello",
        "lang": "en",
        "tool_results": [],
    }

    result = await responder(state)
    assert result is not None
    assert len(captured_prompts) == 1

    sys_prompt = captured_prompts[0]["system_prompt"]
    assert tenant_name in sys_prompt
    assert "intent" not in sys_prompt.lower()
    assert "classify" not in sys_prompt.lower()


async def test_get_tenant_profile_fallback_and_sanitization() -> None:
    # 1. Non-existent tenant fallback
    missing_profile = await get_tenant_profile("non-existent-tenant-xyz")
    assert missing_profile["name"] == "the clinic"
    assert missing_profile["business_type"] == "clinic"

    # 2. Existing tenant with newlines and length cap
    long_name = "  Super Clinic \n with extra   spaces  " + ("x" * 100)
    await get_db()["tenants"].insert_one({
        "_id": "tenant-sanitize-test",
        "name": long_name,
        "business_type": "diagnostic\nlab",
    })
    cleaned_profile = await get_tenant_profile("tenant-sanitize-test")
    assert "\n" not in cleaned_profile["name"]
    assert len(cleaned_profile["name"]) <= 80
    assert cleaned_profile["name"].startswith("Super Clinic with extra spaces")
    assert cleaned_profile["business_type"] == "diagnostic lab"
