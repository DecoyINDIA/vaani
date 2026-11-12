### TASK ID: W1-05

**Title:** Human-readable local appointment times in patient replies

**Priority:** P0

**Objective:** The booking-status reply shows the appointment in the clinic's timezone as `Thu 12 Nov, 10:00 AM`, never a raw UTC ISO string. Provide one reusable formatter.

**Why This Matters:** `inbound.py` replies `Your appointment is confirmed for 2026-11-12T04:30:00` — a naive-UTC `isoformat()` for a 10:00 IST appointment. A patient would arrive 5½ hours off or not at all.

**Prerequisites:** W1-01 (same file; rebase on it).

**Repository Context:**
- Slots store `start`/`end` as **naive UTC** datetimes. Tenants carry `timezone` (default `Asia/Kolkata`).
- `app/workers/inbound.py`, branch `if intent == "booking_status":` (≈ lines 519-534): loads the booking, loads the slot, builds `when = start.isoformat()`.
- The slot-picker labels elsewhere in the file are already local (`slots_get` returns offset-aware ISO strings) and use `strftime("%a %d %b, %I:%M %p")`.

**Files to Inspect:** `app/workers/inbound.py`, `app/agent/tools/slots_get.py` (timezone pattern), `app/models/collections.py` (`Tenants.find_by_id`)

**Files to Modify/Create:**
- Create `app/booking/timefmt.py`.
- Modify `app/workers/inbound.py` (booking_status branch only).
- Create `tests/test_timefmt.py`.

**Detailed Implementation Instructions:**
1. Create `app/booking/timefmt.py` with the two functions below.
2. In the `booking_status` branch, replace the `isoformat()` line: load the tenant with `await Tenants.find_by_id(tenant_id)` (import `Tenants`), compute `tz = tenant_timezone(tenant)`, and set `when = format_local(start, tz)` when `start` is a `datetime`; otherwise keep the existing fallback text `"unknown time"`.
3. Leave the sentence template as is: `f"Your appointment is {booking['status']} for {when}."`
4. Write tests.

**Interfaces & Data Contracts:**
```python
def tenant_timezone(tenant: dict[str, Any] | None) -> ZoneInfo:
    """ZoneInfo(tenant['timezone']) or Asia/Kolkata when missing/invalid."""

def format_local(instant: datetime, tz: ZoneInfo) -> str:
    """Naive datetimes are treated as UTC. Returns e.g. 'Thu 12 Nov, 10:00 AM'."""
```
Format string: `"%a %d %b, %I:%M %p"` (identical to the existing picker labels).

**Edge Cases:** naive input → assume UTC; aware input → convert; invalid timezone string → fall back to `Asia/Kolkata`; date rollover (18:45 UTC → next day 00:15 IST).

**Non-Goals:** No localization of day/month names (that is W2-01). Do not change picker labels, reminders, or any other branch. Do not add fields to bookings.

**Acceptance Criteria:**
- `format_local(datetime(2026, 11, 12, 4, 30), ZoneInfo("Asia/Kolkata")) == "Thu 12 Nov, 10:00 AM"`.
- `format_local(datetime(2026, 11, 12, 18, 45), ZoneInfo("Asia/Kolkata")) == "Fri 13 Nov, 12:15 AM"`.
- `grep -n "isoformat()" app/workers/inbound.py` shows no line that feeds a patient-facing string.
- Full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_timefmt.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Low. A test may assert the old ISO text in a status reply; update it to the formatted value. Rollback = revert.

**Effort & Complexity:** Small, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** The `booking_status` branch no longer exists in `inbound.py`, or `Tenants.find_by_id` is not available.

**Standalone Execution Prompt:**
```
Task W1-05 in the Vaani repo. Read 07-AGENT_CONTEXT.md first. Work on top of W1-01.
Problem: app/workers/inbound.py, branch `if intent == "booking_status":`, sends
start.isoformat() (naive UTC) to the patient.
1. Create app/booking/timefmt.py with
   tenant_timezone(tenant: dict | None) -> ZoneInfo   (default/fallback "Asia/Kolkata")
   format_local(instant: datetime, tz: ZoneInfo) -> str  (naive = UTC; format "%a %d %b, %I:%M %p")
2. In that branch load the tenant via Tenants.find_by_id(tenant_id) and use
   when = format_local(start, tenant_timezone(tenant)) instead of isoformat(). Keep the fallback
   "unknown time" and the sentence wording.
3. Add tests/test_timefmt.py: 04:30 UTC -> "Thu 12 Nov, 10:00 AM" (2026-11-12, Asia/Kolkata);
   18:45 UTC -> "Fri 13 Nov, 12:15 AM"; invalid tz falls back; aware datetime converts.
Do NOT touch other branches, reminders, or slot-picker labels.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if the branch or Tenants.find_by_id is missing.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
