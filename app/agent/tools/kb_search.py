"""Tool — KB retrieval (TRD §3, Week 4 task 4.4).

Atlas Search hybrid (BM25 + vector) over kb_entries. Returns entries with
source_ref so the responder can cite. Retrieval eval target: top-3 hit rate >=90%.
This is the ONLY LLM-adjacent path outside agent/nodes (embedding on write).
"""

from __future__ import annotations

from typing import Any


async def kb_search(tenant_id: str, query: str, *, k: int = 3) -> list[dict[str, Any]]:
    raise NotImplementedError("kb_search — 06-engineering-plan task 4.4")
