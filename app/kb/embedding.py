"""OpenRouter embedding client for KB writes and search queries."""

from __future__ import annotations

from typing import Literal

import httpx

from app.config import settings


async def embed_text(
    text: str, *, input_type: Literal["search_document", "search_query"]
) -> list[float]:
    if settings.use_mock_adapters:
        return [0.0] * settings.kb_embedding_dimensions
    if not settings.openrouter_api_key or not settings.llm_model_embedding:
        raise RuntimeError("Embedding provider is not configured")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": text,
                "input_type": input_type,
                "model": settings.llm_model_embedding,
                "dimensions": settings.kb_embedding_dimensions,
                "encoding_format": "float",
            },
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json().get("data", [])
    vector = data[0].get("embedding") if data and isinstance(data[0], dict) else None
    if (
        not isinstance(vector, list)
        or len(vector) != settings.kb_embedding_dimensions
        or any(not isinstance(value, int | float) for value in vector)
    ):
        raise RuntimeError("Embedding provider returned an invalid vector")
    return [float(value) for value in vector]
