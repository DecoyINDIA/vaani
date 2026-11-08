"""Seed and verify the isolated synthetic backup/restore drill used by CI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.channels.whatsapp import SuppressedRecipientError, send_template
from app.config import settings
from app.gateway.middleware import get_redis
from app.models import base
from app.models.collections import Messages
from app.privacy import identifier_hash, is_suppressed
from app.workers.inbound import GROUP, STREAM, _ensure_group, _process_fallback_queue
from motor.motor_asyncio import AsyncIOMotorClient

DATABASE = "vaani_recovery_drill"
TENANT_ID = "recovery-drill-tenant"
MESSAGE_ID = "recovery-drill-message"
SENDER = "922222222222"
SUPPRESSED = "911111111111"


async def _database() -> Any:
    if (
        os.getenv("RECOVERY_DRILL_CONFIRM") != "synthetic"
        or settings.app_env != "dev"
        or not settings.use_mock_adapters
    ):
        raise RuntimeError("recovery drill requires explicit synthetic dev/mock mode")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    if client.get_default_database().name != DATABASE:
        client.close()
        raise RuntimeError(f"recovery drill database must be exactly {DATABASE}")
    await client.admin.command("ping")
    base._client = client
    return client.get_default_database()


def _payload() -> dict[str, Any]:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "919999999999"},
                            "messages": [
                                {
                                    "id": MESSAGE_ID,
                                    "from": SENDER,
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


async def seed() -> None:
    db = await _database()
    if await db.list_collection_names():
        raise RuntimeError("recovery drill source database must be empty")
    await db["tenants"].insert_one(
        {
            "_id": TENANT_ID,
            "name": "Synthetic Recovery Clinic",
            "wa_number": "919999999999",
            "timezone": "Asia/Kolkata",
        }
    )
    await Messages.accept_inbound_unscoped(MESSAGE_ID, TENANT_ID, _payload())
    await db["erasure_suppression"].insert_one(
        {
            "tenant_id": TENANT_ID,
            "contact_hash": identifier_hash(TENANT_ID, SUPPRESSED),
            "identifier_hashes": [identifier_hash(TENANT_ID, SUPPRESSED)],
            "request_id": "recovery-drill-erasure",
            "created_at": datetime.now(UTC).replace(tzinfo=None),
        }
    )


async def verify(report_path: Path, backup_id: str, started_at_epoch: int) -> None:
    db = await _database()
    queued = await db["messages"].find_one({"_id": MESSAGE_ID, "status": "queued"})
    if not queued:
        raise RuntimeError("restored durable inbound event is missing")
    if not await is_suppressed(TENANT_ID, SUPPRESSED):
        raise RuntimeError("restored erasure suppression marker is missing")

    redis_client = get_redis()
    if await redis_client.dbsize() != 0:
        raise RuntimeError("recovery drill Redis must start empty")
    await _ensure_group(redis_client)
    await redis_client.set("vaani:worker:heartbeat", "recovery-drill", ex=60)
    await _process_fallback_queue()

    recovered = await db["messages"].find_one({"_id": MESSAGE_ID})
    if not recovered or "status" in recovered or "payload" in recovered:
        raise RuntimeError("MongoDB fallback queue did not recover the inbound event")
    if await db["messages"].count_documents({"status": "queued"}) != 0:
        raise RuntimeError("queued work remains after Redis rebuild")
    if not await db["outbound_intents"].find_one(
        {"tenant_id": TENANT_ID, "state": "sent"}
    ):
        raise RuntimeError("recovered event did not complete its outbound intent")
    groups = await redis_client.xinfo_groups(STREAM)
    if not any(group.get("name") == GROUP for group in groups):
        raise RuntimeError("Redis consumer group was not rebuilt")
    if not await redis_client.get("vaani:worker:heartbeat"):
        raise RuntimeError("Redis worker heartbeat was not rebuilt")
    try:
        await send_template(
            TENANT_ID,
            SUPPRESSED,
            "payment_link",
            {},
            operation_key="recovery-drill-suppressed-send",
        )
    except SuppressedRecipientError:
        pass
    else:
        raise RuntimeError("restored erasure marker did not suppress delivery")

    elapsed = int(time.time()) - started_at_epoch
    report = {
        "schema_version": 1,
        "evidence_kind": "synthetic_recovery_drill",
        "scope": "recovery mechanics only; not Atlas/staging RTO or RPO evidence",
        "commit": os.getenv("GITHUB_SHA", "local"),
        "backup_id": backup_id,
        "elapsed_seconds": elapsed,
        "synthetic_rto_target_seconds": 900,
        "synthetic_rto_met": elapsed <= 900,
        "checks": {
            "mongo_dump_restored": True,
            "durable_work_recovered_from_mongo": True,
            "redis_started_empty": True,
            "redis_consumer_group_rebuilt": True,
            "erasure_suppression_reapplied": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    await redis_client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--report", type=Path, required=True)
    verify_parser.add_argument("--backup-id", required=True)
    verify_parser.add_argument("--started-at-epoch", type=int, required=True)
    args = parser.parse_args()
    if args.command == "seed":
        asyncio.run(seed())
    else:
        asyncio.run(verify(args.report, args.backup_id, args.started_at_epoch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
