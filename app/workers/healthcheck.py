"""Container healthcheck for the inbound worker heartbeat."""

from __future__ import annotations

import asyncio
import time

from app.gateway.middleware import get_redis


async def check() -> None:
    try:
        value = await get_redis().get("vaani:worker:heartbeat")
        is_stale = value is None or time.time() - float(value) > 60
    except Exception:
        is_stale = True

    if is_stale:
        from app import audit

        await audit.record(
            "system",
            actor="system",
            event_type="operational_alert",
            payload={"kind": "worker_heartbeat", "status": "stale_or_missing"},
            operation_key=f"heartbeat-alert:{int(time.time() // 60)}",
        )
        raise SystemExit("worker heartbeat is stale")


if __name__ == "__main__":
    asyncio.run(check())
