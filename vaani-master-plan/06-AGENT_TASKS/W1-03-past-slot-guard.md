### TASK ID: W1-03

**Title:** Never offer or hold a slot in the past (or too soon)

**Priority:** P0

**Objective:** `slots_get` returns only slots starting at least `booking_lead_minutes` (default 30) after now, and `hold_slot` refuses any slot whose start is not in the future.

**Why This Matters:** `slots_get` returns every open slot from local midnight, so at 3 pm a patient is offered — and can book — 9 am the same day.

**Prerequisites:** None. (Optional input: discovery DISC-03.)

**Repository Context:**
- `app/agent/tools/slots_get.py`: computes `start_of_day`/`end_of_day` (naive UTC) and `now`; query is `{"practitioner_id", "start": {"$gte": start_of_day, "$lte": end_of_day}, "$or": [open | expired hold]}`. The tenant is already loaded in this function.
- `app/booking/engine.py::hold_slot` (≈ 267-294): atomic `find_one_and_update` with `{"_id": stored_slot_id, "$or": [...]}`; `now` is defined just above the query.
- `confirm_booking`, `move_booking`, `create_booking` all go through `hold_slot`, so one guard covers agent and owner API paths.
- Slot datetimes are naive UTC.

**Files to Inspect:** `app/agent/tools/slots_get.py`, `app/booking/engine.py`, `tests/test_booking_journey.py`, `tests/test_booking_transitions.py`, `tests/integration/test_booking_transactions.py`

**Files to Modify/Create:** `app/agent/tools/slots_get.py`; `app/booking/engine.py` (`hold_slot` only); `tests/test_past_slot_guard.py` (new); fixtures in existing tests that create slots in the past.

**Detailed Implementation Instructions:**
1. `slots_get.py`: read `lead = int(tenant.get("booking_lead_minutes", 30)) if tenant else 30`; clamp to `0..1440`. Compute `earliest = max(start_of_day, now + timedelta(minutes=lead))` and use `"start": {"$gte": earliest, "$lte": end_of_day}`.
2. `engine.py::hold_slot`: add `"start": {"$gt": now}` to the query dict (top level, alongside `_id` and `$or`).
3. Tests (patch "now" by creating slots relative to `datetime.now(UTC)`): slot 2 h ago → not listed, `hold_slot` returns `False`; slot in 10 min → not listed with default lead, but `hold_slot` returns `True`; slot in 2 h → listed and holdable; tenant with `booking_lead_minutes: 0` → slot in 10 min listed.
4. Run the full suite. Where an existing test fails only because its fixture slot is in the past, move that fixture into the future (e.g. `now + timedelta(days=1)`), keeping every assertion intact.

**Interfaces & Data Contracts:** optional tenant field `booking_lead_minutes: int` (default 30). Function signatures unchanged.

**Edge Cases:** requested date entirely in the past → empty list (existing "no slots" handling applies); non-integer `booking_lead_minutes` → fall back to 30; slot starting exactly now → not holdable.

**Non-Goals:** No change to `confirm_booking`, `move_booking`, `cancel_booking`, transactions, or slot generation. No dashboard setting for lead time. No "next available day" suggestion (W3-08).

**Acceptance Criteria:** new tests pass; full suite green with only fixture-date edits to existing tests; replica-set integration test file still imports and collects.

**Verification:**
```bash
uv run pytest -q tests/test_past_slot_guard.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Medium only because of fixture churn. The guard itself is one filter per function. Rollback = revert.

**Effort & Complexity:** Small effort, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** More than ten existing tests fail; any failing test would require changing an assertion (not just a fixture date); a test deliberately books a past slot.

**Standalone Execution Prompt:**
```
Task W1-03 in the Vaani repo. Read 07-AGENT_CONTEXT.md first.
1. app/agent/tools/slots_get.py: only return slots with
   start >= max(start_of_day, now + lead) where lead = tenant.get("booking_lead_minutes", 30)
   minutes (int, clamp 0..1440, fallback 30). Times are naive UTC.
2. app/booking/engine.py hold_slot: add "start": {"$gt": now} to the find_one_and_update filter.
3. Add tests/test_past_slot_guard.py: past slot not listed and not holdable; slot in 10 min not
   listed (default lead) but holdable; slot in 2 h listed and holdable; lead 0 lists the 10-min slot.
4. If existing tests fail only because their fixture slots are in the past, move those fixture
   dates into the future. Never change an assertion.
Do NOT modify confirm/move/cancel logic or slot generation.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if >10 tests fail or any fix would need an assertion change.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
