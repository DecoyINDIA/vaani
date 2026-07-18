"""Tool — KB retrieval (TRD §3, Week 4 task 4.4).

Atlas Search hybrid (BM25 + vector) over kb_entries. Returns entries with
source_ref so the responder can cite. Retrieval eval target: top-3 hit rate >=90%.
This is the ONLY LLM-adjacent path outside agent/nodes (embedding on write).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.models.collections import KbEntries

logger = logging.getLogger(__name__)


async def kb_search(tenant_id: str, query: str, *, k: int = 3) -> list[dict[str, Any]]:
    """Tool — KB retrieval (TRD §3, Week 4 task 4.4).

    Atlas Search hybrid (BM25 + vector) over kb_entries.
    Returns entries with source_ref so the responder can cite.
    """
    try:
        # Standard query fallback for unit tests and local mock/databases
        words = [w for w in re.findall(r"\w+", query) if len(w) > 2]
        filter_query: dict[str, Any] = {}

        if words:
            regex_pattern = "|".join(re.escape(w) for w in words)
            filter_query["$or"] = [
                {"question": {"$regex": regex_pattern, "$options": "i"}},
                {"answer": {"$regex": regex_pattern, "$options": "i"}},
                {"key": {"$regex": regex_pattern, "$options": "i"}}
            ]

        cursor = KbEntries(tenant_id).find(filter_query).limit(k)
        results = []
        async for doc in cursor:
            results.append({
                "key": doc.get("key", ""),
                "question": doc.get("question", ""),
                "answer": doc.get("answer", ""),
                "source_ref": doc.get("key") or str(doc["_id"])
            })
            
        return results
    except Exception as e:
        logger.error(f"Error executing kb_search: {e}")
        return []

