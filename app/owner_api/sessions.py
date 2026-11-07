"""Invitation-bound magic login and rotating owner dashboard sessions."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from pymongo import ReturnDocument

from app.config import settings
from app.models.collections import AuthRateLimits, AuthSessions, Users
from app.owner_api.auth import (
    AuthenticatedUser,
    create_access_token,
    create_purpose_token,
    require_owner_tenant,
    require_user,
    token_hash,
)

router = APIRouter(tags=["auth"])


class InvitePayload(BaseModel):
    user_id: str
    role: str


class TokenPayload(BaseModel):
    token: str


def _decode(token: str, purpose: str) -> dict[str, object]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    if payload.get("purpose") != purpose:
        raise HTTPException(status_code=401, detail="Invalid token purpose")
    return cast(dict[str, object], payload)


async def _new_session(tenant_id: str, user_id: str) -> dict[str, str | int]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.jwt_refresh_ttl_days)
    session_id = secrets.token_urlsafe(24)
    refresh_token, refresh_id = create_purpose_token(
        tenant_id,
        user_id,
        "refresh",
        expires_at,
        session_id=session_id,
    )
    await AuthSessions(tenant_id).insert_one(
        {
            "session_id": session_id,
            "user_id": user_id,
            "refresh_hash": token_hash(refresh_id),
            "created_at": now.replace(tzinfo=None),
            "expires_at": expires_at.replace(tzinfo=None),
        }
    )
    return {
        "access_token": create_access_token(tenant_id, user_id, session_id=session_id),
        "refresh_token": refresh_token,
        "expires_in": settings.jwt_access_ttl_min * 60,
    }


async def _check_rate_limit(
    tenant_id: str,
    kind: str,
    subject: str,
    *,
    limit: int,
    now: datetime,
    window_minutes: int,
) -> None:
    window = f"{now:%Y%m%d%H}:{now.minute // window_minutes}"
    result = await AuthRateLimits(tenant_id).find_one_and_update(
        {"kind": kind, "subject_hash": token_hash(subject), "window": window},
        {
            "$inc": {"attempts": 1},
            "$setOnInsert": {
                "kind": kind,
                "subject_hash": token_hash(subject),
                "window": window,
                "expires_at": (now + timedelta(hours=2)).replace(tzinfo=None),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if result and int(result.get("attempts", 0)) > limit:
        raise HTTPException(status_code=429, detail="Too many authentication attempts")


@router.post("/invitations")
async def create_invitation(
    payload: InvitePayload,
    tenant_id: str = Depends(require_owner_tenant),  # noqa: B008
) -> dict[str, str]:
    if payload.role not in {"owner", "staff"} or not payload.user_id.strip():
        raise HTTPException(status_code=422, detail="A user ID and owner/staff role are required")
    now = datetime.now(UTC)
    user_id = payload.user_id.strip()
    await _check_rate_limit(
        tenant_id,
        "invitation_issue",
        user_id,
        limit=5,
        now=now,
        window_minutes=60,
    )
    expires_at = now + timedelta(minutes=15)
    magic_token, token_id = create_purpose_token(
        tenant_id, user_id, "magic", expires_at
    )
    await Users(tenant_id).update_one(
        {"_id": user_id},
        {
            "$set": {
                "role": payload.role,
                "status": "invited",
                "magic_hash": token_hash(token_id),
                "magic_expires_at": expires_at.replace(tzinfo=None),
                "invited_at": now.replace(tzinfo=None),
            }
        },
        upsert=True,
    )
    return {"magic_token": magic_token}


@router.post("/magic/consume")
async def consume_magic(payload: TokenPayload, request: Request) -> dict[str, str | int]:
    client_host = request.client.host if request.client else "unknown"
    await _check_rate_limit(
        "SYSTEM",
        "magic_consume",
        client_host,
        limit=20,
        now=datetime.now(UTC),
        window_minutes=15,
    )
    claims = _decode(payload.token, "magic")
    tenant_id = str(claims.get("tenant_id", ""))
    user_id = str(claims.get("sub", ""))
    token_id = str(claims.get("jti", ""))
    if not tenant_id or not user_id or not token_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    now = datetime.now(UTC).replace(tzinfo=None)
    result = await Users(tenant_id).find_one_and_update(
        {
            "_id": user_id,
            "status": "invited",
            "magic_hash": token_hash(token_id),
            "magic_expires_at": {"$gt": now},
        },
        {
            "$set": {"status": "active", "activated_at": now},
            "$unset": {"magic_hash": "", "magic_expires_at": ""},
        },
    )
    if not result:
        raise HTTPException(status_code=401, detail="Invitation is invalid or already used")
    return await _new_session(tenant_id, user_id)


@router.post("/refresh")
async def refresh(payload: TokenPayload) -> dict[str, str | int]:
    claims = _decode(payload.token, "refresh")
    tenant_id = str(claims.get("tenant_id", ""))
    user_id = str(claims.get("sub", ""))
    session_id = str(claims.get("session_id", ""))
    token_id = str(claims.get("jti", ""))
    user = await Users(tenant_id).find_one({"_id": user_id, "status": "active"})
    if not user:
        raise HTTPException(status_code=401, detail="User membership is not active")
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)
    rotated, rotated_id = create_purpose_token(
        tenant_id, user_id, "refresh", expires_at, session_id=session_id
    )
    result = await AuthSessions(tenant_id).update_one(
        {
            "session_id": session_id,
            "user_id": user_id,
            "refresh_hash": token_hash(token_id),
            "revoked_at": {"$exists": False},
        },
        {
            "$set": {
                "refresh_hash": token_hash(rotated_id),
                "expires_at": expires_at.replace(tzinfo=None),
                "rotated_at": datetime.now(UTC).replace(tzinfo=None),
            }
        },
    )
    if result.modified_count != 1:
        raise HTTPException(status_code=401, detail="Refresh token is no longer active")
    return {
        "access_token": create_access_token(tenant_id, user_id, session_id=session_id),
        "refresh_token": rotated,
        "expires_in": settings.jwt_access_ttl_min * 60,
    }


@router.post("/logout")
async def logout(
    user: AuthenticatedUser = Depends(require_user),  # noqa: B008
) -> dict[str, str]:
    if not user.session_id:
        raise HTTPException(status_code=400, detail="Token is not associated with a session")
    await AuthSessions(user.tenant_id).update_one(
        {"session_id": user.session_id, "revoked_at": {"$exists": False}},
        {"$set": {"revoked_at": datetime.now(UTC).replace(tzinfo=None)}},
    )
    return {"status": "logged_out"}
