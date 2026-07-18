"""JWT auth for the owner API (TRD §6): 15-min access + refresh. All routes
tenant-scoped; cross-tenant probes must be denied (Week 5 task 5.7, CI suite)."""

from __future__ import annotations


def create_access_token(tenant_id: str, user_id: str) -> str:
    raise NotImplementedError("JWT issue — 06-engineering-plan task 5.7")


async def require_tenant(token: str) -> str:
    """Resolve + verify a bearer token to its tenant_id. Raises on cross-tenant use."""
    raise NotImplementedError("JWT verify — 06-engineering-plan task 5.7")
