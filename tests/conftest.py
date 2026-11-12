"""Tests explicitly opt in to local mock adapters before app imports."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("USE_MOCK_ADAPTERS", "true")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-at-least-32-bytes")
os.environ.setdefault("ENABLE_VOICE", "true")
os.environ.setdefault("ENABLE_PAYMENTS", "true")
os.environ.setdefault("ENABLE_BILLING", "true")

# Ensure dashboard/dist exists so app.main mounts the dashboard SPA
_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if not _dist.exists():
    _dist.mkdir(parents=True, exist_ok=True)
    (_dist / "assets").mkdir(exist_ok=True)
    (_dist / "index.html").write_text(
        '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        '<script type="module" src="/assets/index.js"></script>'
        '<link rel="stylesheet" href="/assets/index.css"></head>'
        '<body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (_dist / "assets" / "index.css").write_text(
        '@media (max-width: 860px) { .login-shell { grid-template-columns: 1fr; } }\n'
        '@media (max-width: 540px) { .workspace { padding-top: 2rem; } }',
        encoding="utf-8",
    )
    (_dist / "assets" / "index.js").write_text(
        'console.log("/api/auth/magic/consume", "/api/conversations", "/api/bookings", '
        '"/api/escalations", "/api/deliveries", "/api/processing", "/api/kb", "/api/settings", '
        '"/api/auth/refresh", "/api/auth/logout");',
        encoding="utf-8",
    )

