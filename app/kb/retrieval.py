"""Tenant-filtered Atlas hybrid retrieval with structured-field degradation."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.kb.embedding import embed_text
from app.models.collections import KbEntries

logger = logging.getLogger(__name__)


def _result(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": document.get("key", ""),
        "question": document.get("question", ""),
        "answer": document.get("answer", ""),
        "source_ref": document.get("key") or str(document["_id"]),
    }


async def _structured_fallback(
    tenant_id: str, fallback_key: str | None
) -> list[dict[str, Any]]:
    if not fallback_key:
        return []
    document = await KbEntries(tenant_id).find_one({"key": fallback_key})
    return [_result(document)] if document else []


async def hybrid_search(
    tenant_id: str,
    query: str,
    *,
    k: int = 3,
    fallback_key: str | None = None,
) -> list[dict[str, Any]]:
    if settings.use_mock_adapters or not settings.llm_model_embedding:
        return await _structured_fallback(tenant_id, fallback_key)
    try:
        vector = await embed_text(query, input_type="search_query")
        documents = await KbEntries(tenant_id).hybrid_search(query, vector, k=k)
        return [_result(document) for document in documents]
    except Exception as error:
        logger.warning(
            "Atlas KB search unavailable; using structured fallback: %s",
            type(error).__name__,
        )
        return await _structured_fallback(tenant_id, fallback_key)
