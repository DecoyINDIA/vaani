"""Container healthcheck for the inbound worker heartbeat."""

from __future__ import annotations

import asyncio
import time

from app.gateway.middleware import get_redis


async def check() -> None:
    value = await get_redis().get("vaani:worker:heartbeat")
    if value is None or time.time() - float(value) > 60:
        raise SystemExit("worker heartbeat is stale")


if __name__ == "__main__":
    asyncio.run(check())
