"""Dry-run-first, resumable KB embedding backfill."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.kb.embedding import embed_text
from app.models.collections import KbEntries


async def reembed(
    *, tenant_id: str | None = None, limit: int = 100, apply: bool = False
) -> dict[str, Any]:
    candidates = await KbEntries.embedding_candidates_unscoped(
        tenant_id=tenant_id, limit=limit
    )
    if not apply:
        return {
            "mode": "dry-run",
            "candidate_count": len(candidates),
            "limit_reached": len(candidates) == limit,
        }

    updated = 0
    for document in candidates:
        vector = await embed_text(
            f"{document['question'].strip()}\n{document['answer'].strip()}",
            input_type="search_document",
        )
        result = await KbEntries(str(document["tenant_id"])).update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "embedding": vector,
                    "embedding_model": settings.llm_model_embedding,
                    "embedding_dimensions": len(vector),
                    "embedded_at": datetime.now(UTC).replace(tzinfo=None),
                }
            },
        )
        updated += result.modified_count
    return {
        "mode": "apply",
        "updated_count": updated,
        "limit_reached": len(candidates) == limit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 1000:
        parser.error("--limit must be between 1 and 1000")
    if args.apply and args.confirm != "REEMBED":
        parser.error("--apply requires --confirm REEMBED")
    print(
        json.dumps(
            asyncio.run(
                reembed(
                    tenant_id=args.tenant,
                    limit=args.limit,
                    apply=args.apply,
                )
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
