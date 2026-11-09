"""Operator utility for fail-closed auth secret rotation and session invalidation."""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from app.models.base import get_db


async def rotate_auth_sessions(*, authorized_by: str, apply: bool = False) -> dict[str, Any]:
    """Inspect or revoke all active authentication sessions to support JWT_SECRET rotation."""
    db = get_db()
    active_count = await db["auth_sessions"].count_documents({"revoked_at": {"$exists": False}})
    total_count = await db["auth_sessions"].count_documents({})

    report = {
        "status": "dry_run" if not apply else "completed",
        "authorized_by": authorized_by,
        "active_sessions_to_revoke": active_count,
        "total_sessions": total_count,
        "timestamp": datetime.now(UTC).isoformat(),
        "next_operator_steps": [
            "1. Generate new 32+ character JWT_SECRET in secure secret store.",
            "2. Update JWT_SECRET environment variable for API and worker services.",
            "3. Restart/redeploy API and worker containers simultaneously from the same image.",
            "4. Verify all prior access and refresh tokens are rejected with HTTP 401.",
            "5. Re-authenticate owners and staff via new magic link issuance.",
        ],
    }

    if not apply:
        return report

    now = datetime.now(UTC).replace(tzinfo=None)
    result = await db["auth_sessions"].update_many(
        {"revoked_at": {"$exists": False}},
        {"$set": {"revoked_at": now, "revoked_reason": "scheduled_secret_rotation"}},
    )
    report["revoked_sessions_count"] = result.modified_count
    return report


def generate_secure_secret() -> str:
    """Generate a cryptographically secure 64-character URL-safe secret."""
    return secrets.token_urlsafe(48)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Authentication secret rotation operator utility")
    parser.add_argument("--authorized-by", required=True, help="Operator ID authorizing rotation")
    parser.add_argument("--apply", action="store_true", help="Apply session revocation")
    parser.add_argument("--generate-key", action="store_true", help="Print a fresh 32+ byte key")

    args = parser.parse_args()
    if args.generate_key:
        print("Generated secret:", generate_secure_secret())

    report = await rotate_auth_sessions(authorized_by=args.authorized_by, apply=args.apply)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
