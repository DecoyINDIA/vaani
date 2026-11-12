"""Container healthcheck for worker/scheduler heartbeats."""

from __future__ import annotations

import asyncio
import sys
import time

from app.gateway.middleware import get_redis


async def check(key: str = "vaani:worker:heartbeat", max_age_seconds: float = 60.0) -> None:
    try:
        value = await get_redis().get(key)
        is_stale = value is None or time.time() - float(value) > max_age_seconds
    except Exception:
        is_stale = True

    if is_stale:
        from app import audit

        bucket = int(time.time() // max(1, int(max_age_seconds)))
        await audit.record(
            "system",
            actor="system",
            event_type="operational_alert",
            payload={"kind": "worker_heartbeat", "component": key, "status": "stale_or_missing"},
            operation_key=f"heartbeat-alert:{key}:{bucket}",
        )
        raise SystemExit(f"{key} heartbeat is stale")


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "vaani:worker:heartbeat"
    max_age = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    asyncio.run(check(key=key, max_age_seconds=max_age))
