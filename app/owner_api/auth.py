"""JWT auth for the owner API (TRD §6): 15-min access + refresh. All routes
tenant-scoped; cross-tenant probes must be denied (Week 5 task 5.7, CI suite).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()


def create_access_token(tenant_id: str, user_id: str) -> str:
    """Create a signed HS256 access token valid for the configured duration."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_ttl_min)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm="HS256"))


async def require_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008 — FastAPI idiom
) -> str:
    """Resolve + verify a bearer token to its tenant_id. Raises on cross-tenant use."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token payload: missing tenant_id")
    return str(tenant_id)
