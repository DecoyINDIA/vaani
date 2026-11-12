# 04 — TARGET ARCHITECTURE

Principle: **evolve in place.** Same single FastAPI app + worker + MongoDB Atlas + Redis. No new services, no framework swap. Each change below is reversible and lands behind tests.

## 1. Runtime topology

```
                 ┌────────── Caddy/TLS (new, compose service) ──────────┐
Meta ──webhook──▶│ api (FastAPI)   /webhooks/meta  /api/*  SPA          │
Razorpay ───────▶│   routers mounted per feature flag                    │
Exotel ─────────▶│   (voice, payments optional)                          │
                 └───────────────┬───────────────────────────────────────┘
                                 │ Mongo `messages` (queue of record) + Redis XADD (wake-up)
                 ┌───────────────▼───────────────┐   ┌────────────────────────┐
                 │ worker  (N async tasks,        │   │ scheduler (same image, │
                 │ per-contact ordering lock)     │   │ `python -m app.workers │
                 └───────────────┬───────────────┘   │  .scheduler`)          │
                                 │                   └────────────────────────┘
                     MongoDB Atlas (txn + Search/Vector)      Redis (private)
```

Changes from today: (1) scheduler split out of the consumer loop into its own entrypoint, same image; (2) worker processes up to `WORKER_CONCURRENCY` events concurrently with a per-`(tenant_id, wa_id)` lock so one patient's messages stay ordered; (3) unique consumer name per process; (4) TLS proxy added to compose; (5) feature flags decide which routers and credentials are required.

## 2. Module boundaries (target)

| Module | Owns | Must not |
|---|---|---|
| `app/gateway/*` | signature verification, durable accept, enqueue | call the agent or send messages |
| `app/workers/inbound.py` | lease, route event to a handler, persist results | contain patient-facing copy or business rules |
| `app/conversation/flows.py` **(new)** | deterministic flows: booking, cancel, status, opt-out, unsupported-media; reads/writes `conversation.flow` | call the LLM |
| `app/agent/*` | understanding (extraction) and grounded phrasing only | mutate bookings or send messages |
| `app/agent/render.py` **(new)** | final text sanitation: strip citation tags, length caps | — |
| `app/i18n/` **(new)** | all patient-facing strings ×4 languages, date/time formatting | — |
| `app/booking/*` | slots, holds, bookings, time rules | know about channels |
| `app/channels/*` | provider I/O, window rules, outbound ledger | decide what to say |
| `app/owner_api/*` | HTTP contracts, authz, view models (joins) | return raw Mongo documents |
| `app/observability.py` **(new)** | Sentry init, JSON logging, `llm_calls` recording | — |

Migration path: flows are **extracted** from `inbound.py` function by function (booking action handler first), with existing tests kept green at each step. No big-bang move.

## 3. Data model deltas (additive only)

| Collection | Field | Type | Purpose |
|---|---|---|---|
| `tenants` | `business_type` | str, default `"clinic"` | prompt/template wording |
| `tenants` | `features` | `{whatsapp: bool, voice: bool, payments: bool}` | per-tenant enablement |
| `tenants` | `booking_lead_minutes` | int, default 30 | earliest bookable slot |
| `tenants` | `avg_booking_value_paise` | int \| null | truthful ROI line; omit line when null |
| `contacts` | `lang_pref` | `en\|hi\|hi-Latn\|or` | last detected language |
| `conversations` | `lang` | same enum | language for deterministic copy |
| `conversations` | `flow` | object (below) | replaces `booking_flow`; reader accepts both during transition |
| `conversations` | `last_msg_at`, `last_inbound_at` | datetime (naive UTC) | inbox sort, lifecycle |
| `conversations` | `closed_at` | datetime | lifecycle |
| `bookings` | `practitioner_id`, `start` | denormalized at confirm | list/calendar without joins |
| `kb_entries` | `key` | slug, unique per tenant | stable citation id |
| `llm_calls` **(new)** | `tenant_id, node, model, latency_ms, prompt_tokens, completion_tokens, ok, ts` (TTL 30 d) | cost + latency telemetry |

**Time convention (unchanged, restated):** store naive UTC datetimes; interpret and render in `tenant.timezone`; never show `isoformat()` to a human.

### `conversation.flow` contract

```json
{
  "kind": "booking | move | cancel",
  "stage": "choose_practitioner | choose_service | choose_slot | awaiting_confirmation | completed | needs_new_search",
  "booking_id": "string | null",
  "practitioner_id": "string", "practitioner_name": "string",
  "service": "string",
  "date": "YYYY-MM-DD",
  "slots": { "<slot_id>": "<ISO-8601 with offset>" },
  "slot_id": "string | null",
  "result": { }, "updated_at": "datetime"
}
```
Store the slot **instant**, not a pre-formatted English label; render the label at send time in `conversation.lang`. A flow older than 30 minutes is ignored.

### Conversation state machine

```
            inbound                    staff takeover / escalate
  (none) ───────────▶  bot  ─────────────────────────────▶  human
                        ▲  ◀──────── return + summary ──────┘
                        │
        24h since last_inbound_at, no open escalation
                        ▼
                     closed   (next inbound creates a new conversation)
```

## 4. Interaction IDs (stable contract between flows and WhatsApp)

| ID | Sent as | Meaning |
|---|---|---|
| `slot:<slot_id>` | list row | pick a slot |
| `prac:<practitioner_id>` | list row | pick a doctor |
| `svc:<index>` | list row | pick a service |
| `booking:confirm` / `booking:cancel` | buttons | confirm / choose again (existing) |
| `cancel:confirm` / `cancel:keep` | buttons | confirm cancellation / keep appointment |
| `menu:book` `menu:hours` `menu:location` `menu:manage` `menu:human` | list rows | capability menu (replaces numbered text menu) |

## 5. Agent design (target)

```
text ──▶ lang_detect ──▶ understand (ONE LLM call, JSON mode, last 3 turns as context)
          returns { intent, confidence, date?, time?, practitioner_hint?, service_hint? }
      ──▶ scope_gate (unchanged topology: medical / out_of_scope / abuse never reach responder)
      ──▶ flows.py for book / reschedule / cancel / status   (no second LLM call)
      ──▶ kb_search ──▶ responder (LLM) ──▶ output_gate ──▶ render.strip_citations   (FAQ only)
```
- Result: booking paths use **one** LLM call; FAQ paths use two. The keyword date parser becomes the offline fallback and the validator for the model's date.
- `query_llm` contract: `async def query_llm(prompt, model, *, system_prompt=None, temperature=0.0, max_tokens=500, json_mode=False, node="") -> str`; shared `httpx.AsyncClient`; total timeout 8 s; one retry on timeout/5xx against `llm_model_fallback_provider`; every call recorded to `llm_calls`.
- Prompts take `{tenant_name}` and `{business_type}`; no tenant literal may appear in `app/agent/` (enforced by a CI grep).
- **Mock-compat constraint:** `get_mock_response` decides "classification" by finding the word `intent` or `classify` in the system prompt, and parses the responder's facts between the literal markers `Grounded Facts:\n` and `\n\nStrict Citation Rule`. Any prompt edit must preserve those markers and keep `intent`/`classify` out of the responder prompt until the mock is replaced.

## 6. Owner API view models (replace raw documents)

```
GET /api/conversations → [{ id, state, channel, last_msg_at, last_message_preview,
                            contact: { id, name, phone }, open_escalation: bool }]
GET /api/bookings?date=YYYY-MM-DD&status= → [{ id, status, service, start (ISO with offset),
                            practitioner: { id, name }, contact: { id, name, phone }, source }]
GET /api/today → { date, bookings: [...], waiting_for_staff: n, failures: n }
GET /api/slots?practitioner_id=&date= → [{ slot_id, start, end }]
GET /api/settings → explicit allow-list: name, timezone, landmark_line, location_pin,
                    business_hours, holiday_calendar, plan, locale_default
POST /api/conversations/{id}/reply → 200 | 409 {code: "window_closed" | "delivery_unknown" | "suppressed"}
```
All datetimes leave the API as ISO-8601 with the tenant offset. Errors carry a machine `code`.

## 7. Security architecture (deltas)

- Feature-flagged runtime validation: a credential is required only if its feature is on (`ENABLE_VOICE`, `ENABLE_PAYMENTS`, `ENABLE_BILLING`).
- Settings read is allow-listed; credential references never leave the server.
- Login: `POST /api/auth/magic/request {phone}` → always 202; if the phone maps to an active membership, send a WhatsApp authentication template with a 15-minute single-use link. Rate-limit per phone hash.
- Tenant WhatsApp tokens move from process env to an encrypted field (`whatsapp.access_token_enc`, AES-GCM, key from `SECRETS_KEY`); env lookup stays as fallback for one release.
- Patient text is passed to the model only in the user turn, wrapped in delimiters; the WhatsApp profile name is never placed in a system prompt.
- Trust `X-Forwarded-For` only from the compose proxy for rate limiting.

## 8. Testing strategy

| Layer | Tooling | Gate |
|---|---|---|
| Unit + flow tests | pytest, mongomock, mock LLM | every PR (exists) |
| Replica-set booking races | real MongoDB in CI | every PR (exists) |
| **Golden transcripts** (new) | scripted multi-turn WhatsApp payloads → asserted outbound payloads, per language | every PR |
| **Real-model eval** (new) | ≥300 labelled utterances ×4 languages; extraction F1, date accuracy, grounding violations | nightly + on prompt/model change; thresholds in 09 |
| Dashboard | vitest + one Playwright smoke | every PR |
| Provider contract | recorded Meta fixtures (exists); **live staging smoke** (new, manual trigger) | before each release |

## 9. Deployment

Single VPS + Compose stays. Add: Caddy service for TLS; `scheduler` service; `COPY ops ./ops` in the image; `worker` scaled with `deploy.replicas` or `--scale` once consumer names are unique. Deploy by digest from GHCR (already produced by CI). Rollback = previous digest; all schema changes in this plan are additive, so no down-migration is needed.

## 10. What is explicitly not in the target

Kubernetes, microservices, a workflow engine, agentic tool-calling, a vector DB other than Atlas, a mobile app, SMS, a patient-facing web app, EMR integration.
