"""Validated, idempotent tenant onboarding from JSON; dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.booking.engine import expand_schedule
from app.models.base import get_db
from app.models.collections import ensure_indexes
from pydantic import BaseModel, Field, field_validator, model_validator

Day = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class Window(BaseModel):
    start: str
    end: str

    @model_validator(mode="after")
    def ordered(self) -> Window:
        try:
            start = time.fromisoformat(self.start)
            end = time.fromisoformat(self.end)
        except ValueError:
            raise ValueError("schedule times must use HH:MM") from None
        if start >= end:
            raise ValueError("schedule window end must be after start")
        return self


class BusinessHours(Window):
    day: Day


class WhatsAppConfig(BaseModel):
    phone_number_id: str = Field(min_length=1)
    access_token_env: str

    @field_validator("access_token_env")
    @classmethod
    def environment_reference_only(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", value):
            raise ValueError("access_token_env must be an environment variable name")
        return value


class PractitionerConfig(BaseModel):
    practitioner_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
    name: str = Field(min_length=1, max_length=120)
    services: list[str] = Field(min_length=1)
    schedule_template: dict[Day, list[Window]]

    @model_validator(mode="after")
    def no_overlapping_windows(self) -> PractitionerConfig:
        for day, windows in self.schedule_template.items():
            ordered = sorted(windows, key=lambda window: window.start)
            if any(
                first.end > second.start
                for first, second in zip(ordered, ordered[1:], strict=False)
            ):
                raise ValueError(f"overlapping practitioner schedule on {day}")
        return self


class TenantConfig(BaseModel):
    tenant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    name: str = Field(min_length=1, max_length=160)
    timezone: str
    plan: Literal["starter", "pro"]
    locale_default: Literal["en", "hi", "hi-Latn", "or"] = "en"
    wa_number: str
    voice_number: str
    landmark_line: str = Field(min_length=1)
    location_pin: str = Field(min_length=1)
    dashboard_url: str = Field(pattern=r"^https://")
    gstin: str = Field(pattern=r"^[0-9A-Z]{15}$")
    whatsapp: WhatsAppConfig
    business_hours: list[BusinessHours] = Field(min_length=1)
    holiday_calendar: list[date] = Field(default_factory=list)
    practitioners: list[PractitionerConfig] = Field(min_length=1)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("timezone must be a valid IANA zone") from None
        return value

    @field_validator("wa_number", "voice_number")
    @classmethod
    def e164_like_phone(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[1-9][0-9]{7,14}", value):
            raise ValueError("phone numbers must be E.164-like digits")
        return value


def load_config(path: Path) -> TenantConfig:
    if path.suffix.lower() != ".json":
        raise ValueError("tenant onboarding accepts JSON files only")
    return TenantConfig.model_validate_json(path.read_text(encoding="utf-8"))


async def apply_config(config: TenantConfig) -> dict[str, int | str]:
    """Upsert declared records only; never delete omitted practitioners or appointments."""
    db = get_db()
    await ensure_indexes()
    now = datetime.now(UTC).replace(tzinfo=None)
    tenant_document = config.model_dump(exclude={"tenant_id", "practitioners"}, mode="json")
    tenant_document["status"] = "active"
    await db["tenants"].update_one(
        {"_id": config.tenant_id},
        {"$set": tenant_document, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    slots_created = 0
    for practitioner in config.practitioners:
        collision = await db["practitioners"].find_one(
            {"_id": practitioner.practitioner_id, "tenant_id": {"$ne": config.tenant_id}}
        )
        if collision:
            raise ValueError("practitioner ID is already owned by another tenant")
        document = practitioner.model_dump(exclude={"practitioner_id"}, mode="json")
        await db["practitioners"].update_one(
            {"_id": practitioner.practitioner_id, "tenant_id": config.tenant_id},
            {"$set": document, "$setOnInsert": {"tenant_id": config.tenant_id}},
            upsert=True,
        )
        slots_created += await expand_schedule(
            config.tenant_id, practitioner.practitioner_id, horizon_days=30
        )
    return {
        "tenant_id": config.tenant_id,
        "practitioners": len(config.practitioners),
        "slots_created": slots_created,
    }


def _summary(config: TenantConfig) -> dict[str, object]:
    return {
        "tenant_id": config.tenant_id,
        "name": config.name,
        "timezone": config.timezone,
        "plan": config.plan,
        "practitioners": len(config.practitioners),
        "whatsapp_secret_reference": config.whatsapp.access_token_env,
    }


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    config = load_config(args.config)
    if not args.apply:
        print(json.dumps({"status": "valid", "dry_run": True, **_summary(config)}, indent=2))
        return
    if args.confirm != config.tenant_id:
        parser.error("--apply requires --confirm matching the tenant_id")
    print(json.dumps({"status": "applied", **await apply_config(config)}, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
