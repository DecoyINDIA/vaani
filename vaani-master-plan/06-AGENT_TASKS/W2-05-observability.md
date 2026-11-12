### TASK ID: W2-05

> **Baseline note:** written against `847d5f5` with Wave 1 merged; locate code by symbol name.

**Title:** Structured JSON logs with tenant/conversation ids, and Sentry error reporting

**Priority:** P1

**Objective:** Every log line from the API and worker is one JSON object carrying `tenant_id`, `conversation_id` and `message_id` when known; unhandled exceptions reach Sentry when `SENTRY_DSN` is set; no phone number or message text appears in either.

**Why This Matters:** `sentry_dsn` is read by `app/config.py` and used nowhere. Logs are free-text with no correlation ids, and two worker log lines print the patient's WhatsApp number. During a pilot there is no way to trace one patient's message through the system.

**Prerequisites:** Wave 1 merged. **Owner approval for one new runtime dependency: `sentry-sdk`.** Do not start without it.

**Repository Context:**
- `app/main.py::create_app()` builds the API; `app/workers/inbound.py::main()` calls `logging.basicConfig(level=logging.INFO)` then `asyncio.run(run())`.
- `app/workers/inbound.py::process_event(fields)` is the per-message entry point; it knows `tenant_id`, `message_id`, and after `_resolve_conversation` the `conversation_id`.
- Log lines in `inbound.py` that include `wa_id`: "Agent produced an empty response for %s" and "24h window closed while replying to %s".
- Dependencies are managed with `uv`; `uv.lock` is committed and CI installs with `--frozen`.

**Files to Inspect:** `app/main.py`, `app/workers/inbound.py`, `app/config.py`, `pyproject.toml`

**Files to Modify/Create:**
- `app/observability.py` — new.
- `app/main.py`, `app/workers/inbound.py` — call the initializer; bind context; fix the two PII log lines.
- `pyproject.toml`, `uv.lock` — via `uv add "sentry-sdk>=2"` only.
- `tests/test_observability.py` — new.

**Detailed Implementation Instructions:**
1. `app/observability.py`:
   - Three `contextvars.ContextVar[str]` (default `""`): tenant, conversation, message.
   - `bind(*, tenant_id=None, conversation_id=None, message_id=None)` sets those given; `clear()` resets all three.
   - `JsonFormatter(logging.Formatter)` emitting keys `ts` (UTC ISO), `level`, `logger`, `msg` (`record.getMessage()`), `service`, plus the three ids when non-empty and `exc_type` when `exc_info` is present. Use `json.dumps(..., ensure_ascii=False)`.
   - `init_observability(service: str)`: replace root handlers with one `StreamHandler` using `JsonFormatter`, level INFO; if `settings.sentry_dsn`, call `sentry_sdk.init(dsn=…, environment=settings.app_env, send_default_pii=False, traces_sample_rate=0.0, before_send=_scrub)`. Idempotent (safe to call twice).
   - `_scrub(event, hint)`: delete `event["request"]["data"]`, `cookies` and `headers` if present; remove frame local variables (`vars`) from every stack frame; add tags from the context vars; return the event.
2. `app/main.py`: call `init_observability("api")` at the top of `create_app()`.
3. `app/workers/inbound.py`: in `main()` replace `logging.basicConfig(...)` with `init_observability("worker")`. In `process_event`: `bind(tenant_id=…, message_id=…)` at the start, `bind(conversation_id=…)` after the conversation is resolved, and `clear()` in a `finally`.
4. Change the two PII log lines to log `conversation_id` instead of `wa_id`.
5. Tests: formatter output parses as JSON and has the required keys; bound ids appear and disappear after `clear()`; `_scrub` removes request data and frame vars and adds tags; `init_observability` with empty DSN does not import-fail or raise; a log call carrying a phone-like argument is **not** altered (document: scrubbing log arguments is out of scope — prevention is by not logging them).

**Interfaces & Data Contracts:**
```python
def init_observability(service: str) -> None
def bind(*, tenant_id: str | None = None, conversation_id: str | None = None,
         message_id: str | None = None) -> None
def clear() -> None
```
Log line example: `{"ts":"2026-11-12T05:01:02Z","level":"INFO","logger":"app.workers.inbound","msg":"…","service":"worker","tenant_id":"clinic_1","conversation_id":"…","message_id":"wamid…"}`

**Edge Cases:** context vars are task-local, so concurrent events (W2-06) do not leak ids into each other; uvicorn installs its own handlers — leave `uvicorn.access` alone, only the root logger changes.

**Non-Goals:** No metrics endpoint, tracing, or log shipping. No request-id middleware. No sweep of other modules' log lines beyond the two named. No change to `audit.py` alerts.

**Acceptance Criteria:** tests pass; `grep -n "wa_id" app/workers/inbound.py | grep -i "logger\."` prints nothing; `uv sync --frozen --extra dev` succeeds with the updated lock; full suite green.

**Verification:**
```bash
uv sync --frozen --extra dev
uv run pytest -q tests/test_observability.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```
Manual (operator, with a real DSN in staging): raise a deliberate exception in a scratch route; confirm the Sentry event has the tags and no request body.

**Risk & Rollback:** Low–medium: tests that capture logs with `caplog` are unaffected (pytest adds its own handler), but a test asserting on stdout log format would break. Rollback = revert including `uv.lock`.

**Effort & Complexity:** Small–medium effort, low reasoning.

**Recommended Agent Tier:** Small agent (medium if the lockfile update misbehaves)

**Escalation Conditions:** Dependency approval not recorded; `uv add` changes unrelated locked versions; `sentry-sdk` fails the repository's `pip-audit`/Trivy gate.

**Standalone Execution Prompt:**
```
Task W2-05 in the Vaani repo. Read 07-AGENT_CONTEXT.md first. Requires recorded owner approval
to add the dependency sentry-sdk (run: uv add "sentry-sdk>=2"; touch nothing else in the lock).
Create app/observability.py with contextvars for tenant/conversation/message ids, bind()/clear(),
a JsonFormatter (keys ts, level, logger, msg, service, ids when set, exc_type), and
init_observability(service) that installs the formatter on the root logger and, if
settings.sentry_dsn is set, sentry_sdk.init(send_default_pii=False, traces_sample_rate=0.0,
before_send=_scrub). _scrub drops request data/cookies/headers and stack-frame vars, adds id tags.
Call init_observability("api") in app/main.py create_app() and init_observability("worker") in
app/workers/inbound.py main() (replacing logging.basicConfig). In process_event bind tenant_id and
message_id at the start, conversation_id once resolved, clear() in finally. Replace wa_id with
conversation_id in the two worker log lines that print it.
Add tests/test_observability.py per the packet.
Do NOT add middleware, metrics, or edit other modules' logging.
Run: uv sync --frozen --extra dev && uv run ruff check . && uv run mypy app && uv run pytest -q
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
