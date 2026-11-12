"""FastAPI application factory.

Mounts the inbound webhook gateway, the tenant-scoped owner API, and the built
dashboard SPA (static). Business logic lives in the routers/nodes it wires up —
this file only assembles the app. See TRD §1 (architecture) and §5 (interfaces).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from app.config import Settings, settings

_DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # API and worker call the same fail-closed runtime guard.
    settings.validate_runtime()

    # Initialize indexes
    from app.models.collections import ensure_indexes
    await ensure_indexes()
    
    yield


def create_app(app_settings: Settings | None = None) -> FastAPI:
    from app.observability import init_observability

    init_observability("api")
    active_settings = app_settings or settings
    app = FastAPI(title="Vaani", version="0.1.0", lifespan=lifespan)

    @app.get("/health", tags=["ops"])
    async def health(response: Response) -> dict[str, Any]:
        # UptimeRobot target (06-engineering-plan 6.1).
        redis_status = "ok"
        mongo_status = "ok"
        
        # Test Redis
        try:
            from app.gateway.middleware import get_redis
            r = get_redis()
            await r.ping()
        except Exception as e:
            redis_status = f"error: {str(e)}"
            
        # Test MongoDB
        try:
            from app.models.base import get_db
            db = get_db()
            # client.admin.command('ping') is the standard way to check mongo connectivity
            await db.client.admin.command("ping")
        except Exception as e:
            mongo_status = f"error: {str(e)}"
            
        redis_ok = redis_status == "ok" or active_settings.app_env == "dev"
        status = "ok" if redis_ok and mongo_status == "ok" else "error"
        if status == "error":
            response.status_code = 503
            
        return {
            "status": status,
            "env": active_settings.app_env,
            "checks": {
                "redis": redis_status,
                "mongodb": mongo_status
            }
        }

    # Inbound webhooks — Meta (P0), Razorpay (P3), Exotel (P2). TRD §5.1.
    from app.gateway import meta
    app.include_router(meta.router, prefix="/webhooks")
    if active_settings.enable_payments or active_settings.enable_billing:
        from app.gateway import razorpay
        app.include_router(razorpay.router, prefix="/webhooks")
    if active_settings.enable_voice:
        from app.gateway import exotel
        app.include_router(exotel.router, prefix="/webhooks")

    # Owner dashboard REST — JWT auth, all tenant-scoped. TRD §5.2.
    from app.owner_api import routes as owner_routes
    from app.owner_api import sessions as owner_sessions
    app.include_router(owner_sessions.router, prefix="/api/auth")
    app.include_router(owner_routes.router, prefix="/api")

    # Built dashboard SPA (Vite output) served behind the same app (ADR-07).
    if _DASHBOARD_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_DASHBOARD_DIST), html=True), name="dashboard")

    return app


app = create_app()
