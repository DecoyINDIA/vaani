"""Smoke tests — the app imports and /health responds. Keeps CI green on an
otherwise-stubbed skeleton so the pipeline is exercised from day one."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
