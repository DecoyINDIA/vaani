"""JWT auth for the owner API (TRD §6): 15-min access + refresh. All routes
tenant-scoped; cross-tenant probes must be denied (Week 5 task 5.7, CI suite).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.models.collections import AuthSessions, Users

security = HTTPBearer()


@dataclass(frozen=True)
class AuthenticatedUser:
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None


def create_access_token(
    tenant_id: str, user_id: str, *, session_id: str | None = None
) -> str:
    """Create a signed HS256 access token valid for the configured duration."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_ttl_min)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "purpose": "access",
        "exp": expire,
    }
    if session_id:
        payload["session_id"] = session_id
    return str(jwt.encode(payload, settings.jwt_secret, algorithm="HS256"))


def token_hash(token_id: str) -> str:
    return hashlib.sha256(token_id.encode()).hexdigest()


def create_purpose_token(
    tenant_id: str,
    user_id: str,
    purpose: str,
    expires_at: datetime,
    *,
    session_id: str | None = None,
) -> tuple[str, str]:
    token_id = secrets.token_urlsafe(32)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "purpose": purpose,
        "jti": token_id,
        "exp": expires_at,
    }
    if session_id:
        payload["session_id"] = session_id
    return str(jwt.encode(payload, settings.jwt_secret, algorithm="HS256")), token_id


async def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008 — FastAPI idiom
) -> AuthenticatedUser:
    """Resolve a token to a current active owner/staff membership."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e

    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    if not tenant_id or not user_id or payload.get("purpose") != "access":
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await Users(str(tenant_id)).find_one({"_id": user_id, "status": "active"})
    if not user:
        raise HTTPException(status_code=401, detail="User membership is not active")
    role = str(user.get("role", ""))
    if role not in {"owner", "staff"}:
        raise HTTPException(status_code=403, detail="User role is not authorized")
    session_id = payload.get("session_id")
    if session_id:
        session = await AuthSessions(str(tenant_id)).find_one(
            {"session_id": str(session_id), "revoked_at": {"$exists": False}}
        )
        if not session:
            raise HTTPException(status_code=401, detail="Session is no longer active")
    return AuthenticatedUser(
        str(tenant_id), str(user_id), role, str(session_id) if session_id else None
    )


async def require_tenant(
    user: AuthenticatedUser = Depends(require_user),  # noqa: B008 — FastAPI idiom
) -> str:
    return user.tenant_id


async def require_owner_tenant(
    user: AuthenticatedUser = Depends(require_user),  # noqa: B008 — FastAPI idiom
) -> str:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")
    return user.tenant_id
