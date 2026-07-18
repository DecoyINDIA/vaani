"""Atlas Search hybrid retrieval (BM25 + vector) over kb_entries (TRD §3).

Backs the kb_search tool. Avoids a separate vector DB at this scale (ADR-03).
"""

from __future__ import annotations

from typing import Any


async def hybrid_search(tenant_id: str, query: str, *, k: int = 3) -> list[dict[str, Any]]:
    raise NotImplementedError("hybrid retrieval — 06-engineering-plan task 4.4")
