### TASK ID: W1-04

**Title:** Two-step cancellation with confirm buttons

**Priority:** P0

**Objective:** A `cancel` intent never cancels by itself. The bot shows the appointment time with two buttons; the booking is cancelled only when the patient taps the confirm button.

**Why This Matters:** Today `inbound.py` cancels the first active booking found for the number as soon as the classifier says `cancel`. One misread message destroys a real appointment, silently.

**Prerequisites:** W1-01, W1-05 (uses `format_local`, `tenant_timezone`).

**Repository Context:**
- `app/workers/inbound.py::process_event`, branch `elif intent == "cancel":` (≈ 535-552) finds a booking with status `confirmed|rescheduled` and immediately calls `booking_cancel(tenant_id, booking_id, contact_id=contact_id)`.
- Interactive replies arrive with `parsed["action_id"]`. `_handle_booking_action(...)` is called before the graph and returns `False` at once when the conversation has no `booking_flow` dict — so cancel actions need their **own** handler.
- `app/channels/whatsapp.py::send_booking_confirmation` is the pattern for a two-button interactive message (window check → `_post` → `audit.record`).
- Helpers in `inbound.py`: `_store_inbound`, `_send_flow_text`, `_record_flow_interactive`, `_now`.
- WhatsApp limits: button title ≤ 20 characters.

**Files to Inspect:** `app/workers/inbound.py`, `app/channels/whatsapp.py`, `app/agent/tools/booking_cancel.py`, `app/booking/timefmt.py`, tests containing cancel journeys (`grep -ln "cancel" tests/*.py`)

**Files to Modify/Create:**
- `app/channels/whatsapp.py` — add `send_cancel_confirmation`.
- `app/workers/inbound.py` — replace immediate cancel; add `_handle_cancel_action`.
- `tests/test_cancel_confirmation.py` — new.
- Existing tests that assert immediate cancellation — update to the two-step flow.

**Detailed Implementation Instructions:**
1. In `whatsapp.py` add `send_cancel_confirmation(tenant_id, wa_id, *, prompt, operation_key)`; copy `send_booking_confirmation`, changing button ids/titles to `cancel:confirm` / "Yes, cancel" and `cancel:keep` / "Keep appointment", and audit `kind` to `"cancel_confirmation"`.
2. In the `elif intent == "cancel":` branch: keep the booking lookup. If none found, keep the existing "could not find" reply. If found:
   a. Load the slot and tenant; `when = format_local(slot["start"], tenant_timezone(tenant))` (fallback `"your appointment"` if no slot).
   b. `$set` on the conversation (filter `{"_id": conversation_db_id, "state": "bot"}`): `cancel_flow = {"stage": "awaiting_confirmation", "booking_id": str(booking["_id"]), "when": when, "created_at": _now()}`.
   c. Store the inbound message with `_store_inbound(..., intent="cancel", confidence=result.get("confidence"))`.
   d. Send `send_cancel_confirmation(prompt=f"Cancel your appointment on {when}?", operation_key=f"cancel-confirm:{message_id or conversation_id}")`, record with `_record_flow_interactive(..., flow="cancel_confirmation", ...)`, then `return`.
3. Add `async def _handle_cancel_action(*, tenant_id, wa_id, contact_id, conversation_id, conversation_db_id, message_id, text, action_id) -> bool` per the pseudocode.
4. In `process_event`, call `_handle_cancel_action(...)` immediately **before** the existing `_handle_booking_action(...)` call; `return` if it returns `True`.
5. Tests (mock adapters): (a) "cancel my appointment" → booking still `confirmed`, slot still `booked`, one interactive outbound; (b) then `cancel:confirm` → booking `cancelled`, slot `open`, text reply; (c) `cancel:keep` → unchanged, text reply, `cancel_flow` removed; (d) `cancel:confirm` with no `cancel_flow` → handler returns `False`; (e) `cancel:confirm` 31 minutes later → not cancelled; (f) duplicate `cancel:confirm` → one cancellation, no error.

**Interfaces & Data Contracts:**
- `conversations.cancel_flow`: `{stage: "awaiting_confirmation"|"completed", booking_id: str, when: str, created_at: datetime}`.
- Reply ids: `cancel:confirm`, `cancel:keep`.
- Operation keys: `cancel-confirm:<message_id|conversation_id>`, `cancel-result:<conversation_id>:<booking_id>`, `cancel-keep:<message_id|conversation_id>`.

**Algorithm / Pseudocode:**
```python
if action_id not in {"cancel:confirm", "cancel:keep"}: return False
conv = await Conversations(tenant_id).find_one({"_id": conversation_db_id})
flow = (conv or {}).get("cancel_flow")
if not isinstance(flow, dict) or flow.get("stage") != "awaiting_confirmation": return False
await _store_inbound(tenant_id, conversation_id, text, message_id, action_id=action_id)
expired = _now() - flow["created_at"] > timedelta(minutes=30)
if action_id == "cancel:keep" or expired:
    unset cancel_flow
    send text: "Okay, your appointment is unchanged."            # key cancel-keep:...
    return True
result = await booking_cancel(tenant_id, flow["booking_id"], contact_id=contact_id)
set cancel_flow.stage = "completed"
send text: "Your appointment on {when} has been cancelled." if result["status"] == "success"
           else "I could not cancel that appointment. Please contact the clinic."
           # key cancel-result:{conversation_id}:{booking_id}
return True
```

**Edge Cases:** conversation taken over by staff between prompt and tap (state filter prevents writes; the human-state check earlier in `process_event` already stores and returns); booking already cancelled (engine returns the cancelled booking → success wording is fine); several active bookings → still the first found (multi-booking choice is out of scope).

**Non-Goals:** No typed "yes/haan" handling. No localization (W2-01). No change to `booking_cancel`, the engine, or reschedule flow.

**Acceptance Criteria:** tests (a)–(f) pass; `grep -n "booking_cancel(" app/workers/inbound.py` shows the call only inside `_handle_cancel_action`; full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_cancel_confirmation.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Medium — existing acceptance tests encode one-step cancel and must be rewritten to send the button reply; do not delete them. Rollback = revert.

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** More than five existing tests need rewriting; `send_booking_confirmation` no longer matches the described pattern; the `cancel` branch has moved out of `process_event`.

**Standalone Execution Prompt:**
```
Task W1-04 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet fully. Base on W1-05.
Goal: the "cancel" intent must ask for confirmation with buttons; only a tap on
"cancel:confirm" cancels the booking.
- whatsapp.py: add send_cancel_confirmation(tenant_id, wa_id, *, prompt, operation_key), a copy
  of send_booking_confirmation with buttons cancel:confirm "Yes, cancel" and cancel:keep
  "Keep appointment", audit kind "cancel_confirmation".
- inbound.py: in `elif intent == "cancel":` stop calling booking_cancel. Save
  conversation.cancel_flow {stage:"awaiting_confirmation", booking_id, when, created_at},
  store the inbound, send the buttons with prompt "Cancel your appointment on {when}?"
  (when = format_local(slot start, tenant tz)), record it, return.
- Add _handle_cancel_action (pseudocode in the packet) and call it just before
  _handle_booking_action in process_event. 30-minute expiry. Idempotent operation keys as listed.
- Add tests/test_cancel_confirmation.py covering cases (a)-(f) in the packet; rewrite existing
  tests that expect one-step cancellation so they send the cancel:confirm button reply.
Do NOT change booking_cancel.py, app/booking/engine.py, or the reschedule flow. English copy only.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if >5 existing tests need rewriting.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
