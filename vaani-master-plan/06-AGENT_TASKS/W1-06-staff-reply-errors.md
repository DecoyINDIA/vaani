### TASK ID: W1-06

**Title:** Staff reply: map delivery errors to clear 4xx/5xx responses

**Priority:** P1

**Objective:** `POST /api/conversations/{id}/reply` returns a structured error instead of HTTP 500 when the message cannot be sent, and the dashboard shows the message text.

**Why This Matters:** `send_freeform` raises `WindowClosedError` when the patient's last message is older than 24 hours. The route does not catch it, so staff see a generic failure exactly when they most need to know why.

**Prerequisites:** None.

**Repository Context:**
- `app/owner_api/routes.py::reply_to_conversation` (≈ lines 118-174) calls `send_freeform(tenant_id, wa_id, text, operation_key=f"staff-reply:{request_id}")` with no `try`.
- `app/channels/whatsapp.py` defines `WindowClosedError`, `AmbiguousDeliveryError`, `SuppressedRecipientError` (all subclass `RuntimeError`) and raises plain `RuntimeError` for provider HTTP errors and missing tenant credentials.
- `dashboard/src/App.tsx::api()` builds its error with `new Error(body.detail || …)`; a dict `detail` would render as `[object Object]`.

**Files to Inspect:** `app/owner_api/routes.py`, `app/channels/whatsapp.py`, `dashboard/src/App.tsx` (function `api`), `tests/test_browser_owner_acceptance.py`

**Files to Modify/Create:** `app/owner_api/routes.py`; `dashboard/src/App.tsx` (the `api` function only); `tests/test_staff_reply_errors.py` (new).

**Detailed Implementation Instructions:**
1. Import the three exception classes in `routes.py`.
2. Wrap the `send_freeform` call. Catch in this order (specific before general) and raise `HTTPException(status_code=…, detail={"code": …, "message": …})`:

| Exception | Status | code | message |
|---|---|---|---|
| `WindowClosedError` | 409 | `window_closed` | "The patient's last message was more than 24 hours ago. WhatsApp only allows approved templates now." |
| `SuppressedRecipientError` | 409 | `suppressed` | "This contact has been erased and cannot be messaged." |
| `AmbiguousDeliveryError` | 409 | `delivery_unknown` | "This reply may already have been sent. Check Delivery issues before retrying." |
| `RuntimeError` | 502 | `provider_error` | "WhatsApp could not deliver the reply. Try again shortly." |

3. Do not store a `Messages` row when the send fails (the existing upsert stays after the `try`).
4. In `App.tsx::api`, compute the error text as: string `detail` → itself; object `detail` → its `message`; otherwise the existing fallback. Change only that expression.
5. Tests: monkeypatch `app.owner_api.routes.send_freeform` to raise each exception; assert status and `detail["code"]`; assert no outbound message row was created.

**Interfaces & Data Contracts:** error body `{"detail": {"code": str, "message": str}}`. Success body unchanged: `{"status": "sent", "deduplicated": bool}`.

**Edge Cases:** `WindowClosedError` is a `RuntimeError` — order of `except` clauses matters; never include the phone number or exception string in `message`.

**Non-Goals:** No template-send fallback. No changes to `whatsapp.py`. No other routes. No other dashboard edits.

**Acceptance Criteria:** four new tests pass; existing success-path tests unchanged; `npm run lint && npm run build` pass.

**Verification:**
```bash
uv run pytest -q tests/test_staff_reply_errors.py tests/test_browser_owner_acceptance.py
uv run ruff check . && uv run mypy app && uv run pytest -q
cd dashboard && npm ci && npm run lint && npm run build
```

**Risk & Rollback:** Low. Rollback = revert.

**Effort & Complexity:** Small, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** The exception classes are not subclasses of `RuntimeError`, or the reply route has moved.

**Standalone Execution Prompt:**
```
Task W1-06 in the Vaani repo. Read 07-AGENT_CONTEXT.md first.
In app/owner_api/routes.py, reply_to_conversation calls send_freeform without error handling.
Wrap it and raise HTTPException(detail={"code","message"}):
  WindowClosedError -> 409 window_closed; SuppressedRecipientError -> 409 suppressed;
  AmbiguousDeliveryError -> 409 delivery_unknown; any other RuntimeError -> 502 provider_error.
Catch specific classes before RuntimeError. Use the fixed messages in the packet table; never
echo phone numbers or exception text. Do not write the Messages row on failure.
In dashboard/src/App.tsx change only the error-text expression inside api(): if body.detail is
a string use it, if it is an object use body.detail.message, else keep the fallback.
Add tests/test_staff_reply_errors.py (monkeypatch app.owner_api.routes.send_freeform).
Do NOT edit app/channels/whatsapp.py or other routes.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q ; cd dashboard && npm ci &&
npm run lint && npm run build
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
