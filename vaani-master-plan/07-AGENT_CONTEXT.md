# 07 — AGENT CONTEXT PACKAGE

Give this file, plus one task packet, to every implementing agent. It replaces repository rediscovery. Baseline commit: `847d5f5`.

## Owner decisions for Waves 1-2 (12 November 2026)

- Execute every written Wave 1 packet, INT-1, every written Wave 2 packet, and INT-2. Do not invent or implement the unwritten Wave 3-4 packets.
- Work directly on `main`, one packet per commit, after the concurrent remediation task has finished and the working tree is clean. Do not create task branches or worktrees.
- The `sentry-sdk>=2` runtime dependency is approved. Use the Sentry Developer free plan; keep tracing disabled, send no default PII, and scrub event data as W2-05 requires.
- The real-model thresholds in `09-QUALITY_GATES.md` section 5 are ratified.
- Do not prescribe, record, or hardcode candidate model identifiers. No OpenRouter credential is available for this implementation run. Build the provider-facing code, harness, dataset, and workflow, but record credentialed model runs and their dependent acceptance evidence as pending external gates.
- Missing external credentials must not pause code implementation. They do prevent claiming the W2-02 real run, W2-03 before/after comparison, INT-2, or pilot readiness as complete.
- Hindi/Odia copy and the synthetic evaluation dataset will receive human review after implementation. Their sign-off remains mandatory before the pilot.

## Project in five lines

Vaani is a multi-tenant AI front desk for Indian clinics. Patients message a clinic's WhatsApp number; Vaani answers FAQs from an approved knowledge base and books appointments with tap-based pickers; staff take over from a web dashboard. Languages: `en`, `hi` (Devanagari), `hi-Latn` (Hinglish), `or` (Odia). Not yet live: every test runs on mocks. Correctness for the patient outranks new features.

## Stack

Python 3.12 · FastAPI · Motor (MongoDB Atlas) · Redis Streams · LangGraph · OpenRouter via `httpx` · PyJWT · pydantic-settings · `uv` for deps. Dashboard: React 18 + Vite + TypeScript + Tailwind (`dashboard/`). Docker Compose (api, worker, redis). CI: `.github/workflows/ci.yml`.

## Repository map (only what matters)

```
app/config.py                 all env settings; validate_runtime() fail-closed guard
app/main.py                   FastAPI factory; mounts routers + dashboard/dist
app/models/base.py            TenantScoped accessor, serialize_mongo, mongo_id_candidates
app/models/collections.py     one accessor class per collection; ensure_indexes()
app/gateway/meta.py           WhatsApp webhook → durable accept → Redis wake-up
app/gateway/{exotel,razorpay}.py   voice and payment webhooks (frozen — do not touch)
app/workers/inbound.py        consumer loop; process_event(); booking flow; scheduler loop
app/workers/{reminders,escalations,weekly_summary,billing}.py   scheduled jobs
app/agent/graph.py            lang_detect → intent → scope_gate → tool_router → responder → output_gate → handoff
app/agent/nodes/*.py          one file per node
app/agent/llm.py              query_llm() + rule-based MOCK used by all tests
app/agent/templates/__init__.py   static safety/refusal templates ×4 languages
app/agent/tools/*.py          slots_get, booking_create/move/cancel, kb_search, escalate, payment_link_create
app/booking/engine.py         expand_schedule, hold_slot, confirm_booking, cancel_booking, move_booking
app/booking/relative_date.py  "kal/parso/next monday" → date
app/channels/whatsapp.py      send_freeform, send_template, send_slot_picker, send_booking_confirmation
app/channels/voice/*          voice session (frozen)
app/kb/{embedding,retrieval}.py   hybrid KB search with structured fallback
app/owner_api/{auth,sessions,routes}.py   JWT auth, magic link, dashboard REST
app/audit.py                  audit.record(); operational alerts
dashboard/src/App.tsx         the whole SPA
ops/*.py                      operator CLIs (onboard_tenant, dpdp_delete, …)
tests/                        pytest; tests/conftest.py forces USE_MOCK_ADAPTERS=true
evals/                        mock eval harness + datasets
```

## Non-negotiable rules

1. **Tenant scope.** All DB access goes through an accessor in `app/models/collections.py` constructed with `tenant_id` (`Bookings(tenant_id).find_one(...)`). Never write `db[...]` outside `app/models/` — CI greps for it. Methods named `*_unscoped` are the only exceptions and already exist.
2. **IDs.** Mongo `_id` may be an `ObjectId` or a legacy string. To match an external string id use `{"_id": {"$in": mongo_id_candidates(value)}}` or `await Accessor(tenant_id).resolve_id(value)`. Return data to HTTP/tools through `serialize_mongo(...)`.
3. **Time.** Store naive UTC: `datetime.now(UTC).replace(tzinfo=None)`. Convert with `ZoneInfo(tenant.get("timezone", "Asia/Kolkata"))` only for interpretation and display. Never show `isoformat()` to a patient.
4. **Sending.** Patient/staff messages go only through `app/channels/whatsapp.py` functions, each with a deterministic `operation_key` (idempotency). Free-form and interactive sends raise `WindowClosedError` outside the 24-hour window; templates are allowed any time but must be in `TEMPLATE_PACK` with variables matching `TEMPLATE_CONTRACTS`.
5. **Compliance topology.** `medical_question`, `out_of_scope`, `abuse`, `complaint` must never reach the `responder` node. Do not add edges that bypass `scope_gate`.
6. **Side effects are idempotent.** Bookings use `request_id`; sends use `operation_key`; audits may pass `operation_key`.
7. **No tenant literals.** No clinic name, city, or specialty in code under `app/` (the mock in `app/agent/llm.py` is the temporary exception).
8. **Secrets and PII.** Never log tokens, phone numbers or message text at INFO or above. Never put PII in `operational_alert` payloads.
9. **Config.** Only `app/config.py` reads environment variables (existing exception: `whatsapp._tenant_credentials`).

## Mock-LLM coupling you must not break

`app/agent/llm.py::get_mock_response` powers every test:
- It treats a call as **classification** if the system prompt contains the word `intent` or `classify`. The responder prompt must therefore contain neither word.
- It extracts the user message with the regex `(?:user message|patient latest message): '(.*)'`. Keep those exact phrases in the prompts.
- It reads responder facts between the literal `Grounded Facts:\n` and `\n\nStrict Citation Rule`. Keep both markers.
- Do not edit `get_mock_response` unless your packet says so.

## Conventions

- `from __future__ import annotations`; full type hints; mypy `strict`; ruff rules `E,F,I,UP,B`, line length 100.
- Async everywhere; no blocking I/O.
- Tests: `pytest-asyncio` auto mode; put new tests in `tests/test_<topic>.py`; use the existing fixtures in `tests/conftest.py`; never require network.
- Logging: `logger = logging.getLogger(__name__)`; `%s` formatting.
- Dashboard: function components, no new dependencies without the packet saying so.

## Verification commands (verified from CI)

```bash
uv sync --frozen --extra dev
uv run ruff check .
uv run mypy app
uv run pytest -q
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json
```
```bash
cd dashboard && npm ci && npm run lint && npm run build
```
Tenant-isolation grep (must print nothing):
```bash
grep -rnE 'db\[[^]]+\]\.(find|insert|update|delete)' app --include='*.py' | grep -v '^app/models/'
```

## Key shapes

- **Conversation:** `{_id, tenant_id, contact_id, channel: "wa"|"voice", state: "bot"|"human"|"closed", started_at, booking_flow?}`
- **`booking_flow`:** `{stage: "choose_slot"|"awaiting_confirmation"|"completed"|"needs_new_search", kind: "create"|"move", booking_id, practitioner_id, practitioner_name, service, date, slots: {slot_id: label}, slot_id?}`
- **Slot:** `{_id, tenant_id, practitioner_id, start, end, status: "open"|"held"|"booked", hold_owner?, hold_expiry?, booking_id?}` (naive UTC)
- **Booking:** `{_id, tenant_id, slot_id, contact_id, service, status: "confirmed"|"rescheduled"|"cancelled", request_id, ts}`
- **Contact:** `{_id, tenant_id, wa_id, phone?, name, last_inbound_ts, messaging_opt_out?}`
- **Tenant:** `{_id (slug), name, timezone, wa_number, landmark_line, location_pin, holiday_calendar[], business_hours[], plan, whatsapp: {phone_number_id, access_token_env}}`
- **Interactive reply ids:** `slot:<id>`, `booking:confirm`, `booking:cancel`
- **AgentState:** `tenant_id, conversation_id, channel, text, lang, intent, confidence, tool_results, response, escalate, agent_error, retry_count, regenerate`

## Frozen areas (do not modify unless the packet names them)

`app/gateway/exotel.py`, `app/channels/voice/*`, `app/gateway/razorpay.py`, `app/billing/*`, `ops/*` (except where named), `.github/workflows/*`, `docs/production-*.md`, `uv.lock` (changes only via `uv add` when the packet permits a dependency).

## Mandatory return format

```
TASK: <id>
FILES CHANGED: <path — one-line reason> …
SUMMARY: <≤6 lines>
TESTS RUN: <exact commands>
RESULTS: <pass/fail counts copied from output>
DEVIATIONS FROM PACKET: <none | list>
REMAINING ISSUES: <none | list>
EVIDENCE: <new test names; grep output where the packet asks for it>
```

## Stop and escalate when

- A file or symbol named in the packet does not exist or differs materially from the packet's description.
- An existing test fails for a reason unrelated to your change, or you would need to weaken an assertion in a security/tenant-isolation/booking-race test.
- The change needs a new dependency, a new collection, or an edit to a frozen area not named in the packet.
- You have made two failed attempts at the same failing check. Report what you tried; do not try a third approach.
