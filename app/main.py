"""FastAPI application factory.

Mounts the inbound webhook gateway, the tenant-scoped owner API, and the built
dashboard SPA (static). Business logic lives in the routers/nodes it wires up —
this file only assembles the app. See TRD §1 (architecture) and §5 (interfaces).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings

_DASHBOARD_DIST = Path(__file__).parent.parent / "dashboard" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Vaani", version="0.1.0")

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        # UptimeRobot target (06-engineering-plan 6.1).
        return {"status": "ok", "env": settings.app_env}

    # Inbound webhooks — Meta (P0), Razorpay (P3), Exotel (P2). TRD §5.1.
    from app.gateway import meta, razorpay
    app.include_router(meta.router, prefix="/webhooks")
    app.include_router(razorpay.router, prefix="/webhooks")

    # Owner dashboard REST — JWT auth, all tenant-scoped. TRD §5.2.
    from app.owner_api import routes as owner_routes
    app.include_router(owner_routes.router, prefix="/api")

    # Built dashboard SPA (Vite output) served behind the same app (ADR-07).
    if _DASHBOARD_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_DASHBOARD_DIST), html=True), name="dashboard")

    return app


app = create_app()
