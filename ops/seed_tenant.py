"""Seed the fixed synthetic demo tenant in an explicit dev/test environment.

Creates the tenant + KB entries + practitioner schedules + holiday calendar
(Odisha festival set) + location pin + landmark line. Target: each onboarding
<=1 day wall clock, seed a demo clinic in <1 min.

This is not a production onboarding command and accepts no tenant configuration.
Usage: python -m ops.seed_tenant --demo
"""

from __future__ import annotations

import argparse
import asyncio

from app.booking.engine import expand_schedule
from app.config import settings
from app.models.base import get_db


async def seed_demo_async() -> None:
    if settings.app_env != "dev" or not settings.use_mock_adapters:
        raise RuntimeError("demo seeding requires dev with USE_MOCK_ADAPTERS=true")
    db = get_db()
    tenant_id = "test_tenant"

    # 1. Seed Tenant
    await db["tenants"].delete_many({"_id": tenant_id})
    await db["tenants"].insert_one({
        "_id": tenant_id,
        "name": "Sharma Dental Clinic",
        "vertical": "clinic",
        # Demo tenant only: this is where a business is described to the agent.
        # Any kind of business works; omit the block for neutral defaults.
        "business_profile": {
            "business_type": "dental clinic",
            "customer_term": "patient",
            "staff_term": "doctor",
            "restricted_topics": ["medical advice, diagnosis or medicine recommendations"],
            "restricted_examples": ["mere daant me dard hai kaunsi dawai lu?"],
        },
        "wa_number": "919999999999",
        "voice_number": "919999999998",
        "plan": "starter",
        "status": "active",
        "locale_default": "hi",
        "timezone": "Asia/Kolkata",
        "business_hours": [
            {"day": "monday", "start": "09:00", "end": "18:00"},
            {"day": "tuesday", "start": "09:00", "end": "18:00"},
            {"day": "wednesday", "start": "09:00", "end": "18:00"},
            {"day": "thursday", "start": "09:00", "end": "18:00"},
            {"day": "friday", "start": "09:00", "end": "18:00"},
            {"day": "saturday", "start": "09:00", "end": "18:00"}
        ],
        "holiday_calendar": [
            "2026-06-16",  # Raja festival Odisha
            "2026-06-25",  # Rath Yatra Odisha
            "2026-11-09"   # Nuakhai Odisha
        ],
        "landmark_line": "Opposite HDFC Bank, Main Market",
        "location_pin": "https://maps.google.com/?q=20.296,85.824",
        "created_at": 0
    })

    # 2. Seed Practitioner (Dr. Sharma)
    practitioner_id = "sharma_dr"
    await db["practitioners"].delete_many({"_id": practitioner_id})
    await db["practitioners"].insert_one({
        "_id": practitioner_id,
        "tenant_id": tenant_id,
        "name": "Dr. Sharma",
        "services": ["Tooth Extraction", "Root Canal", "Cleaning"],
        "schedule_template": {
            "monday": [{"start": "09:00", "end": "09:30"}, {"start": "10:00", "end": "10:30"}],
            "tuesday": [{"start": "09:00", "end": "09:30"}, {"start": "10:00", "end": "10:30"}],
            "wednesday": [{"start": "09:00", "end": "09:30"}],
            "thursday": [{"start": "09:00", "end": "09:30"}],
            "friday": [{"start": "09:00", "end": "09:30"}],
            "saturday": [{"start": "09:00", "end": "09:30"}],
            "sunday": []
        }
    })

    # 2b. Expand schedule_template into concrete bookable slots (normally the
    # nightly job's work) — without this a fresh tenant has zero slots.
    await expand_schedule(tenant_id, practitioner_id, horizon_days=14)

    # 3. Seed KB FAQs
    await db["kb_entries"].delete_many({"tenant_id": tenant_id})
    await db["kb_entries"].insert_many([
        # Questions carry Hindi/Odia variants so the BM25/regex fallback in
        # kb_search can retrieve entries for non-English queries too.
        {
            "tenant_id": tenant_id,
            "key": "faq_hours",
            "question": "What are the clinic timings / hours? क्लिनिक का समय क्या है? क्लीनिक कब खुला रहता है? କ୍ଲିନିକ୍ ସମୟ କ'ଣ?",
            "answer": "Sharma Dental Clinic is open from 9:00 AM to 6:00 PM Monday through Saturday. [source_ref: faq_hours]",
            "ts": 0
        },
        {
            "tenant_id": tenant_id,
            "key": "faq_fees",
            "question": "What is the consultation fee? फीस / शुल्क कितनी है? ଫିସ୍ କେତେ?",
            "answer": "The consultation fee is Rs 500. [source_ref: faq_fees]",
            "ts": 0
        },
        {
            "tenant_id": tenant_id,
            "key": "faq_location",
            "question": "Where is the clinic located? What is the address? क्लिनिक का पता क्या है? କ୍ଲିନିକ୍ ଠିକଣା କ'ଣ?",
            "answer": "Sharma Dental Clinic is located near Main Market, Bhubaneswar. Landmark: Opposite HDFC Bank. [source_ref: faq_location]",
            "ts": 0
        }
    ])

    print(f"Seeded demo clinic successfully for tenant: {tenant_id} in < 1s")


def seed_demo() -> None:
    asyncio.run(seed_demo_async())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.demo:
        parser.error("only explicit --demo seeding is supported")
    seed_demo()

