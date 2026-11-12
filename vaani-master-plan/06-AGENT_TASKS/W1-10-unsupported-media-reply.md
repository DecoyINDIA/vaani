### TASK ID: W1-10

**Title:** Reply to unsupported message types; maintain `last_msg_at`

**Priority:** P1

**Objective:** (1) A voice note, image, video, document, sticker, location or contact card gets one polite reply instead of silence. (2) Every WhatsApp inbound updates `conversations.last_msg_at` so the staff inbox sorts by recency.

**Why This Matters:** `process_event` returns early with "Skipping non-text" — the patient hears nothing. Voice notes are common among the target users. Separately, the inbox sorts on `last_msg_at`, which WhatsApp inbound never sets.

**Prerequisites:** W1-04 (same file).

**Repository Context:**
- `app/workers/inbound.py::_parse_message` returns `{wa_id, text, profile_name, action_id, message_type}`; `text` is empty for non-text types.
- `process_event` begins: `if not parsed or not parsed["text"]: … return`.
- `_resolve_conversation` upserts the contact, finds or inserts the conversation, returns `(conversation_id, state, conversation_db_id, contact_id)`.
- `_store_inbound(...)` writes the message with `type` = `"interactive"` or `"text"`.
- When `conversation_state == "human"` the bot must stay silent (store only).

**Files to Inspect:** `app/workers/inbound.py`, `tests/test_inbound_loop.py`

**Files to Modify/Create:** `app/workers/inbound.py`; `tests/test_unsupported_media.py` (new).

**Detailed Implementation Instructions:**
1. Add a module constant `UNSUPPORTED_TYPES = frozenset({"audio", "image", "video", "document", "sticker", "location", "contacts"})` and
   `UNSUPPORTED_REPLY = "Sorry, I can only read text messages right now. Please type your question and I will help."`
2. Give `_store_inbound` an optional keyword `message_type: str | None = None`; when provided it is used for the stored `type`. Existing callers are unaffected.
3. Change the early return in `process_event`:
   - `if not parsed: return` (unchanged behaviour for unparseable payloads).
   - If `parsed["text"]` is empty and `parsed["message_type"] in UNSUPPORTED_TYPES`: resolve the conversation; `_store_inbound(tenant_id, conversation_id, "", message_id, message_type=parsed["message_type"])`; if state is `"human"` return; otherwise `_send_flow_text(tenant_id, wa_id, conversation_id, UNSUPPORTED_REPLY, f"unsupported:{message_id or conversation_id}")` and return.
   - If `parsed["text"]` is empty and the type is anything else (reaction, system, unknown): log at INFO and return.
4. In `_resolve_conversation`, set `last_msg_at` to `_now()`: add it to the `$set` when an existing conversation is found (one `update_one` on `{"_id": convo["_id"]}`; merge with the existing `open → bot` update), and include `"last_msg_at": _now()` in the inserted document.
5. Tests: audio message → exactly one outbound text equal to `UNSUPPORTED_REPLY` and a stored inbound with `type == "audio"`; same audio event processed twice → still one outbound (operation key dedup); conversation in `human` state → stored, no outbound; reaction → no outbound, nothing stored; any text inbound → conversation has `last_msg_at`.

**Interfaces & Data Contracts:** `conversations.last_msg_at: datetime` (naive UTC). Stored inbound `type` may now be one of `UNSUPPORTED_TYPES`.

**Edge Cases:** 24-hour window is open by definition right after an inbound (the contact's `last_inbound_ts` is refreshed in `_resolve_conversation` before the send); image with caption → still treated as unsupported in this task; missing `message_id` → key falls back to `conversation_id`.

**Non-Goals:** No transcription or media download. No localization (W2-01). No audit/metering changes.

**Acceptance Criteria:** tests above pass; full suite green; no behaviour change for text and interactive messages.

**Verification:**
```bash
uv run pytest -q tests/test_unsupported_media.py tests/test_inbound_loop.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Low. Rollback = revert.

**Effort & Complexity:** Small, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** `_parse_message` no longer returns `message_type`; an existing test asserts that non-text events produce no stored message.

**Standalone Execution Prompt:**
```
Task W1-10 in the Vaani repo. Read 07-AGENT_CONTEXT.md first. Base on W1-04.
File: app/workers/inbound.py.
A) Non-text messages. process_event currently returns early when parsed["text"] is empty.
   Change: if text is empty and parsed["message_type"] is one of
   audio,image,video,document,sticker,location,contacts -> resolve the conversation, store the
   inbound with that type (add optional kwarg message_type to _store_inbound), and unless the
   conversation state is "human" send exactly one text via _send_flow_text:
   "Sorry, I can only read text messages right now. Please type your question and I will help."
   operation key f"unsupported:{message_id or conversation_id}". Other empty-text types: log, return.
B) In _resolve_conversation set conversations.last_msg_at = _now() on both the found path and
   the insert path.
Add tests/test_unsupported_media.py (audio reply once; duplicate event -> one outbound; human
state -> stored only; reaction ignored; last_msg_at set on text inbound).
No localization, no media download, no other behaviour changes.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
