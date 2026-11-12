# TRD — Project Vaani: Technical Requirements & Architecture

**Version:** 2.0 | **Date:** 18 Jul 2026 | **Owner:** Subham Jena (Xolver) | **Status:** Draft — v2.0 adds interactive messaging, degradation ladder (§9), quality flywheel (§10)

---

## 1. Architecture Overview

```
                    ┌─────────────────────────────────────────────┐
                    │                CHANNELS                     │
                    │  WhatsApp (Meta Cloud API via BSP)          │
                    │  Voice (Exotel/Plivo SIP) [Phase 2]         │
                    └──────────────┬──────────────────────────────┘
                                   │ webhooks / media streams
                    ┌──────────────▼──────────────────────────────┐
                    │  GATEWAY LAYER (FastAPI)                    │
                    │  • webhook verification (Meta signature)    │
                    │  • tenant resolution (number → tenant_id)   │
                    │  • rate limiting, dedup (message idempotency)│
                    │  • enqueue → Redis Streams                  │
                    └──────────────┬──────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────────┐
                    │  AGENT CORE (LangGraph worker pool)         │
                    │  Nodes:                                     │
                    │   1. lang_detect  2. intent_classifier      │
                    │   3. scope_gate   4. tool_router            │
                    │   5. responder    6. output_scope_check     │
                    │   7. handoff_manager                        │
                    │  Tools: kb_search, slots_get, booking_create│
                    │         booking_move, booking_cancel,       │
                    │         payment_link_create, escalate       │
                    └───────┬─────────────────┬───────────────────┘
                            │                 │
              ┌─────────────▼──────┐  ┌───────▼────────────────────┐
              │ DATA (MongoDB Atlas)│  │ LLM LAYER (OpenRouter)    │
              │ + Redis (queue,     │  │ primary: fast frontier    │
              │   locks, session)   │  │ fallback: second provider │
              └─────────────────────┘  │ classifier: small model   │
                                       └────────────────────────────┘
                    ┌─────────────────────────────────────────────┐
                    │  OWNER SURFACE                              │
                    │  • Dashboard: React (Vite) SPA + FastAPI    │
                    │  • Escalation alerts: WhatsApp template     │
                    └─────────────────────────────────────────────┘
```

**Design principles:** (1) channel-agnostic agent core — voice and WhatsApp share the same graph; (2) scope enforcement in code, not prompts alone; (3) every side-effect is a tool call, every tool call is audited; (4) tenant_id threaded through every function signature — no ambient tenant context.

## 2. Stack Decisions (ADR summaries)

### ADR-01: Agent framework — LangGraph
**Decision:** LangGraph over raw orchestration or CrewAI/AutoGen.
**Rationale:** Deterministic state machine fits a scoped agent (compliance requires predictable paths); checkpointing gives conversation persistence; team already has LangGraph architecture work from the voice-system PRD. **Trade-off:** heavier than a hand-rolled router; accepted for handoff/interrupt semantics.

### ADR-02: LLM access — OpenRouter, model-pinned
**Decision:** OpenRouter with pinned models per node: small/cheap model for intent classification + scope check; frontier model for response generation; automatic failover to a second provider.
**Rationale:** Cost flexibility (₹-sensitive unit economics), no single-vendor outage risk, easy A/B of models per language. **Constraint:** all prompts and evals must be model-portable (no provider-specific features in core paths). **Data note:** verify zero-retention/opt-out flags per provider for DPDP posture; log this in the compliance register.

### ADR-03: Datastore — MongoDB Atlas (Mumbai region) + Redis
**Decision:** MongoDB Atlas M10+ in ap-south-1; Redis (Upstash or self-hosted) for queue (Streams), slot locks, and session cache.
**Rationale:** Team fluency (LawFlow stack), flexible tenant schemas, Atlas Search for KB retrieval (BM25 + vector) avoids a separate vector DB at this scale. **Data residency:** India region mandatory (DPDP posture + customer optics).

### ADR-04: WhatsApp access — Meta Cloud API via existing BSP
**Decision:** Use current BSP relationship; do NOT use on-prem API or unofficial libraries.
**Rationale:** Compliance surface (Jan 2026 policy) is safest through an approved BSP; unofficial WhatsApp libraries = instant ban risk. **Consequence:** conversation-based pricing is a COGS line — must be metered per tenant.

### ADR-05: Voice pipeline (Phase 2) — Exotel SIP + Sarvam-first STT/TTS
**Decision:** Exotel for Indian numbers/SIP (fallback: Plivo); STT bake-off between Sarvam and Deepgram on Hindi/Odia phone audio (8kHz, noisy); TTS: Sarvam (Indic) primary, ElevenLabs fallback for English.
**Rationale:** Indic accuracy is the product; decide on data, not brand. **Latency budget (hard):** STT partials ≤300ms; LLM first token ≤700ms; TTS first audio ≤400ms; end-to-end first response ≤2.0s. If budget unachievable with chosen vendors, use streaming + filler acknowledgments ("जी, एक second...") — measured, not assumed.
**v2 addition:** the bake-off includes one realtime **speech-to-speech** model (GPT-realtime-class / Gemini-Live-class) as a third architecture option alongside the two cascaded pipelines. If a duplex model wins on latency + Hindi/Odia accuracy at ≤₹4/min, the cascade becomes the fallback, not the default. Same scope gates apply regardless of architecture — the s2s model's tool calls route through the identical LangGraph tools, and out-of-scope handling stays templated (the s2s system prompt cannot be the compliance boundary).

### ADR-06: Hosting — single VPS/container platform first
**Decision:** Railway/Render or a Hetzner/DO VPS with Docker Compose (API, workers, Redis); Atlas managed separately. Move to k8s NEVER before 100 tenants.
**Rationale:** 25-tenant scale is trivial traffic (<5 req/s peak). Ops simplicity > premature scale. **Consequence:** single-region SPOF accepted for pilot; mitigation = daily backups + 15-min restore runbook.

### ADR-07: Dashboard — React SPA, not Expo app
**Decision:** Vite + React + shadcn/Tailwind SPA served behind the same FastAPI.
**Rationale:** One codebase, no app-store cycle, owners live on desktop-WhatsApp+phone-browser. Expo app deferred (P2).

## 3. Data Model (MongoDB collections)

```
tenants        { _id, name, vertical?, business_profile?, wa_number, voice_number, plan, status,
                 locale_default, business_hours[], holiday_calendar[],  // national + state festival closures, owner-editable
                 gstin?, landmark_line, location_pin, created_at }
               // business_profile { business_type, customer_term, staff_term, restricted_topics[], restricted_examples[], avg_booking_value? (INR; prices recovered bookings in reports) }
               // — all optional; industry-neutral defaults apply when absent. Implemented in app/agent/profile.py.
               // `vertical` is a legacy label and is not read by the agent.
users          { _id, tenant_id, role: owner|staff, phone, wa_id, name, notif_prefs }
contacts       { _id, tenant_id, wa_id, phone, name?, lang_pref, consent:
                 { status, ts, notice_version }, tags[], created_at,
                 profile: { preferred_practitioner?, last_service?, last_visit?,
                            visit_cadence_days?, csat_avg? } }   // returning-customer memory (F-20)
conversations  { _id, tenant_id, contact_id, channel: wa|voice, state:
                 bot|human|closed, assigned_to?, started_at, last_msg_at }
messages       { _id, tenant_id, conversation_id, direction, type, text,
                 media_ref?, lang, intent?, confidence?, latency_ms, ts }
kb_entries     { _id, tenant_id, kind: field|faq, key?, question?, answer,
                 embedding, version, updated_by, ts }
practitioners  { _id, tenant_id, name, services[], schedule_template }   // staff members or bookable resources; collection name kept, rename deferred (needs a data migration)
slots          { _id, tenant_id, practitioner_id, start, end, status:
                 open|held|booked|blocked, hold_expiry?, version }   // optimistic lock
bookings       { _id, tenant_id, slot_id, contact_id, service, status:
                 confirmed|rescheduled|cancelled|no_show|completed,
                 source: wa|voice|manual, payment_id?, reminders_sent[], ts }
payments       { _id, tenant_id, booking_id?, contact_id, rzp_link_id, amount,
                 status, created_at, paid_at? }
escalations    { _id, tenant_id, conversation_id, reason, sla_notified_at,
                 first_human_response_at?, resolved_at?, resolver? }
audit_log      { _id, tenant_id, actor: agent|user|owner|system, event_type,
                 payload, conversation_id?, ts }        // append-only, TTL 90d default
usage_meters   { tenant_id, period, wa_conversations, voice_minutes,
                 llm_tokens_in/out, cost_estimate }
eval_candidates{ _id, tenant_id, conversation_id, source: escalation|thumbs_down|
                 gate_rejection|random_sample, status: queued|labeled|added|rejected, ts }
prompt_registry{ _id, node, lang, version, hash, eval_report_ref, active, ts }
                 // active prompt set is a deployable artifact; rollback = flip pointer
```

**Indexes:** every collection compound-indexed on (tenant_id, …). `slots` unique on (tenant_id, practitioner_id, start). Booking creation uses `findOneAndUpdate(status:"open" → "held")` with 120s hold_expiry, then confirm — race-safe by construction.

## 4. Agent Design

### 4.1 Intent taxonomy (closed set — compliance boundary)
`greet, faq_hours, faq_location, faq_services, faq_fees, faq_staff, book, reschedule, cancel, booking_status, payment_query, reminder_response, human_request, complaint, restricted_advice, smalltalk_min, out_of_scope, abuse`

Rules baked into graph:
- `restricted_advice` → templated refusal + booking offer + escalate flag. Never generated freeform. What counts as restricted comes from the tenant's `business_profile.restricted_topics`; the default list is medical, legal and financial advice. The legacy labels `medical_question` and `faq_doctor` are still accepted from the model and mapped to `restricted_advice` and `faq_staff`.
- Prompts and reply wording are built from the tenant's `business_profile` at request time; static templates are industry-neutral.
- `out_of_scope` → static template + capability menu. **LLM responder node is never invoked.**
- `complaint`/`abuse` → escalate after one templated de-escalation.
- `smalltalk_min` → single canned pleasantry, then redirect to menu (prevents open-domain drift).

### 4.2 Scope enforcement (two gates, both mandatory)
1. **Input gate:** classifier (small model, temperature 0, few-shot per language) must emit an intent from the closed set with confidence ≥ threshold; below threshold twice → handoff.
2. **Output gate:** post-generation check — response must (a) cite a KB entry or tool result for any factual claim (fee/time/service/address), (b) contain no content outside intent scope. Fail → regenerate once → else fallback template. This makes Meta-policy compliance and anti-hallucination a code path, not a prompt hope.

### 4.3 Language handling
- Detect per message (fastText/lingua + script heuristics); Hinglish = Latin-script Hindi handled as its own register.
- Respond in the user's language/register; templates maintained in all four (hi, en, hi-Latn, or).
- **Relative-date resolver (India rule):** "kal" (yesterday/tomorrow), "parso", "agle [weekday]" are ambiguous — resolver picks the future interpretation, and the agent MUST echo weekday + date for confirmation before any booking tool call. Enforced in the booking tool contract (tool rejects bookings without a `date_confirmed` flag).
- **Time conventions:** parse 12-hour colloquial forms ("shaam ko 4 baje", "subah 10", "dopahar") and Indic numerals; always render times back as "4:00 PM (shaam)" style — unambiguous but colloquial.
- **Register:** default to respectful forms (आप / ଆପଣ) in all templates; never तू/tum in system copy.
- Voice notes: transcribe (same STT as Phase 2); confidence <0.75 → ask to type or escalate.

### 4.4 Handoff protocol
Trigger → `conversations.state = human` → bot silenced for that thread → WhatsApp template alert to on-duty staff (with deep link to inbox) → SLA timer. Staff "Resolve & return" flips state back to `bot` with a context summary injected into agent memory. All transitions audited.

## 5. External Interfaces

### 5.1 Inbound webhooks
- `POST /webhooks/meta` — signature-verified (X-Hub-Signature-256), idempotent on message_id, 200-fast + async processing (Meta requires <5s ack).
- `POST /webhooks/razorpay` — payment link events, signature-verified.
- `POST /webhooks/exotel` (Phase 2) — call events + media stream socket.

### 5.2 Owner API (dashboard, JWT auth, all tenant-scoped)
```
GET  /api/conversations?state=&page=        GET  /api/conversations/{id}/messages
POST /api/conversations/{id}/takeover       POST /api/conversations/{id}/return
GET  /api/bookings?from=&to=                POST /api/bookings (manual)
PATCH/api/bookings/{id}                     GET  /api/escalations?open=true
GET/PUT /api/kb                              GET/PUT /api/settings
GET  /api/metrics/summary?period=           GET  /api/audit/export?from=&to=
```

### 5.3 Outbound messaging rules (Meta policy)
- Free-form replies only inside the 24-hour customer service window.
- Outside window: pre-approved **utility** templates only (booking confirmation, reminders, payment link). No marketing templates in v1.
- Template pack (submit Week 2): `booking_confirm`, `booking_reminder_24h`, `booking_reminder_2h`, `payment_link`, `escalation_alert_staff`, `weekly_summary_owner`, `daily_brief_owner` (draft, not yet submitted), `consent_notice`, `missed_call_bridge` (F-16, utility category — opt-in gated).
- **Interactive messages (v2):** inside the 24h window, reply buttons and list messages are ordinary service messages — they are the **default booking UX** (F-18: list picker for slots, buttons for Confirm/Change/Cancel), not an enhancement. WhatsApp Flows (F-19) for the native booking form; Flow JSON versioned in repo, tested in draft mode before publish. CSAT prompt (F-21) sent in-window immediately on resolution — no template needed. Mark-as-read + typing indicator fired ≤1s after every inbound (perceived-latency budget).

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Latency | WhatsApp: p50 ≤3s, p95 ≤10s message→reply; mark-as-read + typing indicator ≤1s after receipt. Voice: see ADR-05 budget. |
| Availability | 99.5% pilot target (monthly); 99.9% from Phase 3 via the degradation ladder (§9) — the bar is "never silent", not "never degraded". Status page not required; owner WhatsApp broadcast on incidents >15 min. |
| Throughput | Design for 50 tenants × 100 conv/day; peak 5 msg/s. Queue absorbs bursts; workers horizontal-scalable. |
| Security | TLS everywhere; secrets in env/secret manager; JWT (15-min access + refresh); webhook signature verification mandatory; per-tenant API isolation tests in CI; OWASP top-10 checklist before pilot. |
| Data protection | India-region storage; PII fields (phone, name) encrypted at rest (Atlas CSFLE for phone numbers); audit log append-only; retention 90d default, per-tenant configurable; deletion pipeline for DPDP requests (≤7 days SLA). |
| Observability | Structured JSON logs; per-node latency + token metrics; Sentry for errors; daily cost report per tenant (LLM + BSP + telephony) — **cost visibility is a launch blocker**, not an afterthought. |
| Testing | Eval suite: ≥300 labeled utterances across 4 languages × intent set, run in CI; containment/accuracy regression gate (no deploy if intent F1 drops >2pts). Booking race test (500 concurrent). Prompt changes require eval pass. |
| Backup/DR | Atlas continuous backup; Redis is rebuildable state only; restore runbook tested once before pilot (RTO 15 min, RPO 1 hr). |

## 7. Cost Model (per-tenant, Starter plan, 1,000 conversations/mo — verify Q1)

**Pricing regime note (Q1):** Meta switched to per-message pricing in July 2025 — inbound-triggered service replies are **free**, utility templates inside the 24h window are free, and only templates sent outside the window are billed (~₹0.115/msg India list rate; BSP adds markup). Vaani's traffic mix (mostly inbound service + in-window confirmations) means the Meta line is dominated by reminders and missed-call bridges, not conversations.

| Line | Estimate/mo |
|------|-------------|
| Meta per-message charges (out-of-window utility: ~2 reminders × ~150 bookings + bridges) | ₹40–150 + BSP markup (verify — Q1) |
| BSP platform fee (per-tenant amortized) | ₹100–250 |
| LLM (classifier + responder, ~4 turns/conv avg) | ₹250–500 |
| Infra amortized (VPS, Atlas, Redis / tenants) | ₹150–300 |
| **COGS total** | **₹550–1,200** |
| Revenue (Starter, ex-GST) | ₹2,999 |
| **Gross margin** | **60–82% → must land >60%; if not, raise price or cap conversations** |

Voice (Pro): STT+TTS+LLM+telephony ≈ ₹2.5–4.0/min → 300 included minutes ≈ ₹750–1,200 COGS on ₹4,000 price delta. Margin holds only with per-minute overage billing — non-negotiable in plan design.

## 8. Explicit Build/Buy/Defer

- **Buy:** BSP messaging, telephony, STT/TTS, payments (Razorpay), error tracking.
- **Build:** agent graph, scope gates, booking engine, KB+RAG, dashboard, metering, audit, degradation ladder, quality flywheel.
- **Defer:** vector DB, k8s, data warehouse, SSO, mobile app, EHR integrations.

## 9. Resilience — Degradation Ladder (never go silent)

A top-1% agent's failure mode is graceful, honest, and fast. Every dependency has a scripted fallback; the customer always gets something useful within the latency budget. "Sorry, try later" is a P1 bug; silence is a P0 bug.

| Failure | Degradation step |
|---------|------------------|
| Primary LLM slow/down | OpenRouter failover to second provider (ADR-02) → if both down, **menu mode**: static capability menu + button-driven booking. Menu mode needs no LLM at all — the list picker (F-18) + slots/booking tools are fully deterministic, so bookings keep flowing during an LLM outage. |
| Classifier down | Keyword/regex pre-router covers the top intents (book, cancel, hours, fees, human); everything else → handoff. |
| Atlas Search degraded | KB falls back to exact-field lookup for structured fields (hours, fees, address); free-text FAQs answer "I'll check with our team" + escalate. |
| Redis down | Webhook still 200-acks; messages persist to a Mongo fallback queue; workers drain on recovery. A message is never dropped. |
| Meta send API down | Retry with backoff; >5 min sustained → owner alerted out-of-band per runbook. |
| Voice vendor down (P2) | Calls forward straight to the owner's phone, as if Vaani weren't there — the business loses nothing it didn't already lack. |

Circuit breakers per vendor (open after 5 consecutive failures, half-open probe at 30s). Degraded state is visible on the dashboard and in the daily health/cost report. **Chaos drill before pilot:** kill each dependency in staging once, verify the ladder holds; scripted in `ops/`.

## 10. Quality Flywheel (the compounding moat)

The eval suite (§6) is the gate; the flywheel is what makes it compound. This — not features — is the durable answer to copycat risk (R7): anyone can wrap the same APIs; nobody else has the labeled vernacular corpus across local trades.

1. **Auto-capture:** every escalation, every 👎 CSAT (F-21), every output-gate rejection, plus a 5% random sample, auto-create `eval_candidates` rows. Zero manual collection.
2. **Label loop:** weekly 30-min labeling ritual (Subham + native speakers as needed) converts candidates → eval-set entries. Target: eval set grows ≥50 utterances/week during pilot.
3. **Shadow replay:** every prompt/model/taxonomy change replays the last 7 days of production traffic offline (inputs only, no sends) and diffs intent/gate/response decisions against what production did. Ship only if strictly better or neutral per language — catches per-language regressions the static eval set misses.
4. **LLM-as-judge:** nightly judge pass scores a transcript sample on groundedness, register (respectful आप/ଆପଣ forms), and language-match; trends on the quality dashboard; >2pt drop = alarm before owners notice.
5. **Corpus → moat:** consented, anonymized utterances accumulate into the vernacular corpus (DPDP-clean per Compliance §3 — anonymization pipeline, no cross-tenant profiling). At ~10K labeled utterances, fine-tune the intent classifier: cost per classification drops, F1 rises, and each new language pack starts from a better base.

Prompt versions live in `prompt_registry` with eval-report refs; the active prompt set is a deployable artifact — rollback = flip the version pointer, no redeploy.
