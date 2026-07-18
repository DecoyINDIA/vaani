# Engineering Build Plan — Project Vaani (End-to-End)

**Version:** 2.0 | **Date:** 18 Jul 2026 | **Owner:** Subham Jena (Xolver)
**Scope:** everything from `git init` to 25 tenants in production. Business phasing, gates, and budget live in [03-build-plan.md]; this doc is the engineering execution layer under it. **Execution discipline: every task here runs as a TDD loop per [07-tdd-loops.md] — tests first, loop closes only on green, next loop blocked until then.** Stack per TRD ADRs 01–07 (LangGraph, OpenRouter, MongoDB Atlas Mumbai + Redis, Meta Cloud API via BSP, Exotel, single VPS).

---

## 0. Repo & System Layout

One monorepo (`vaani/`), one deployable unit for pilot scale. Split NEVER before 100 tenants.

```
vaani/
├── pyproject.toml            # uv-managed; Python 3.12
├── docker-compose.yml        # api, worker, redis (Atlas is external)
├── .github/workflows/ci.yml  # lint → typecheck → unit → eval gate → build
├── app/
│   ├── main.py               # FastAPI app factory; mounts routers + dashboard static
│   ├── config.py             # pydantic-settings; ALL env in one place
│   ├── gateway/              # webhooks: meta.py, razorpay.py, exotel.py (P2)
│   │   └── middleware.py     # signature verify, tenant resolution, idempotency
│   ├── agent/
│   │   ├── graph.py          # LangGraph definition (7 nodes per TRD §1)
│   │   ├── nodes/            # lang_detect.py, intent.py, scope_gate.py,
│   │   │                     # responder.py, output_gate.py, handoff.py
│   │   ├── tools/            # kb_search, slots_get, booking_create/move/cancel,
│   │   │                     # payment_link_create, escalate — every side-effect
│   │   ├── prompts/          # versioned, model-portable; one file per node per lang
│   │   └── templates/        # static replies: out_of_scope, medical_refusal,
│   │                         # de_escalation × {hi, en, hi-Latn, or}
│   ├── booking/              # slot engine: schedule expansion, holiday calendar,
│   │                         # atomic hold/confirm, relative-date resolver
│   ├── kb/                   # KB CRUD, embedding pipeline, Atlas Search retrieval
│   ├── channels/
│   │   ├── whatsapp.py       # send API, template registry, 24h-window tracker
│   │   └── voice/            # P2: exotel session, stt.py, tts.py, barge_in.py
│   ├── billing/              # usage meters, per-tenant cost rollup, GST invoice gen
│   ├── owner_api/            # dashboard REST (TRD §5.2), JWT auth
│   ├── models/               # pydantic + mongo collection accessors (tenant_id
│   │                         # REQUIRED positional arg on every accessor — no default)
│   ├── audit.py              # append-only writer; single choke point
│   └── workers/              # Redis Streams consumers: inbound, reminders, weekly_summary
├── dashboard/                # Vite + React + shadcn SPA → built into app static
├── evals/
│   ├── dataset/              # utterances.jsonl (lang, text, expected_intent, expected_facts)
│   ├── run_evals.py          # intent F1, scope-gate accuracy, hallucination check
│   └── voice_corpus/         # Phase-0 recordings + transcripts (STT bake-off)
├── ops/
│   ├── seed_tenant.py        # tenant + KB + schedule + holiday calendar from a YAML sheet
│   ├── restore_runbook.md    # tested before pilot (RTO 15m / RPO 1h)
│   └── dpdp_delete.py        # data-principal erasure pipeline (≤7d SLA)
└── tests/                    # unit + integration; race test lives here
```

**Non-negotiable code rules (enforced in review + CI):**
1. `tenant_id` is an explicit parameter on every DB accessor; a lint rule greps for raw `db[collection].find` outside `models/`.
2. Every outbound message and tool call goes through `audit.py` — no direct sends.
3. No LLM call outside `agent/nodes/` and `agent/tools/kb_search`. The responder is unreachable for `out_of_scope`/`medical_question` intents *by graph topology*, not by prompt.
4. Prompt/template/taxonomy changes fail CI unless `evals/` passes (intent F1 ≥ threshold, hallucination = 0).

---

## 1. Phase 1 Engineering — WhatsApp MVP (Weeks 3–6)

Ordering principle: **walking skeleton first** — a message travels the full pipe end-to-end in week 3 with stubs, then each stub is replaced. Never build a layer that can't be exercised from a real WhatsApp message.

### Week 3 — Walking skeleton (Milestone M1.1)

| # | Task | Definition of done |
|---|------|--------------------|
| 3.1 | Repo, CI, Docker Compose, dev/prod env split, secrets via env | `docker compose up` gives working API locally; CI green on empty test suite |
| 3.2 | Meta webhook: signature verify, <5s ack, message_id idempotency (Redis SETNX, 24h TTL), tenant resolution by `wa_number` | Duplicate webhook delivery produces exactly one processed message (test) |
| 3.3 | Redis Streams queue + inbound worker with consumer group, dead-letter after 3 retries | Kill worker mid-message → message reprocessed, not lost |
| 3.4 | Mongo collections + indexes from TRD §3 (incl. `holiday_calendar`, `gstin`, `landmark_line`, `location_pin` on tenants); `seed_tenant.py` v0 | Seed script creates a demo clinic in <1 min |
| 3.5 | LangGraph skeleton: lang_detect (lingua + script heuristic) → intent_classifier (small model, few-shot per lang, temp 0) → scope_gate → responder **stub** (echoes intent) → output_gate **stub** | Live on test number: reply names detected language + intent |
| 3.6 | Eval harness v0 + 150-utterance seed set (write 40/lang from interview transcripts + synthetic) | `python evals/run_evals.py` prints per-lang F1; CI gate wired at ≥85% |
| 3.7 | WhatsApp send wrapper + 24h-window tracker (last inbound ts per contact; free-form only inside window); mark-as-read + typing indicator fired on every inbound (perceived-latency budget ≤1s) | Attempted out-of-window free-form send raises, forces template path; typing indicator visible ≤1s in manual device test |

**Exit:** M1.1 — echo-with-intent bot on test number, F1 ≥85% on seed set.

### Week 4 — Booking engine + KB grounding (Milestone M1.2)

| # | Task | Definition of done |
|---|------|--------------------|
| 4.1 | Schedule expansion: practitioner `schedule_template` → concrete `slots` rows, nightly job, **holiday calendar blocks generation**; owner-editable closures | Slots never generated on Raja/Rath Yatra/custom closure days (test) |
| 4.2 | Atomic booking: `findOneAndUpdate(status:"open"→"held")` + 120s hold expiry + confirm; `booking_create/move/cancel` tools | 500-concurrent race test: 0 double-bookings (CI, runs nightly not per-commit) |
| 4.3 | Relative-date resolver: "kal/parso/agle X" → future date; booking tool **rejects** calls without `date_confirmed=true`; agent echoes weekday + date in user's language before confirming | Eval cases: 20 relative-date utterances, 100% confirmed-before-booked |
| 4.4 | KB: structured fields + FAQ entries, embedding on write, Atlas Search hybrid (BM25 + vector) retrieval tool | Retrieval eval: top-3 hit rate ≥90% on 50 seeded Q→entry pairs |
| 4.5 | Real responder: KB/tool-grounded generation with **citation requirement** (every factual claim carries `source_ref`); output_gate v1: reject uncited fee/time/service/address claims → regenerate once → fallback template | Hallucination eval (30 trap questions where KB lacks the answer): 0 fabricated facts |
| 4.6 | Static template flows: medical refusal, out-of-scope + capability menu, de-escalation, location pin + landmark reply — ×4 languages, respectful register | Graph test: `medical_question` and `out_of_scope` paths never touch the LLM responder node |
| 4.7 | Interactive booking UX (F-18): list-message slot picker (top 8 + "more"), reply-button Confirm/Change/Cancel, free-text fallback path; per-step conversion counters | Booking completable in ≤3 taps after intent on a real device; picker→confirm conversion visible in daily report |

**Exit:** M1.2 — end-to-end booking in Hindi + Hinglish on test number; race test green.

### Week 5 — Handoff, dashboard, compliance plumbing (Milestone M1.3)

| # | Task | Definition of done |
|---|------|--------------------|
| 5.1 | Handoff state machine: triggers (human_request, 2× low-confidence, medical/complaint, abuse) → `state=human`, bot silenced, staff WhatsApp template alert ≤30s, SLA timers in `escalations` | Simulated trigger → alert received on staff test phone <30s |
| 5.2 | "Resolve & return": staff action flips `state=bot`, context summary injected into thread memory | Post-return message answered by bot with awareness of human resolution |
| 5.3 | Dashboard v1 (Xolver-facing acceptable): conversations + transcripts, bookings calendar, escalation inbox, settings (hours/services/fees/holidays), KB editor, daily counters | 2 non-technical testers complete UAT checklist unaided |
| 5.4 | Audit log at the choke point: message, intent, gate decisions, tool calls, handoffs; export endpoint | Random transcript reconstructable end-to-end from audit alone |
| 5.5 | Usage metering + daily per-tenant cost report (LLM tokens, Meta billable messages, infra amortized) | Cost report lands on Subham's WhatsApp daily — launch blocker per TRD §6 |
| 5.6 | DPDP: first-contact consent notice (per lang, versioned), consent state on contact, `dpdp_delete.py` erasure pipeline | Erasure run removes contact PII across all collections; audit entry retained pseudonymized |
| 5.7 | Eval set → 300 utterances; JWT auth (15m access + refresh); tenant-isolation tests in CI (every owner_api route probed cross-tenant) | F1 ≥90%; cross-tenant probe suite = 100% denied |
| 5.8 | Security pass: OWASP top-10 checklist, rate limits, secrets audit | Checklist filed in repo `ops/` |
| 5.9 | CSAT (F-21) + quality flywheel v0: post-resolution 👍/👎 buttons; 👎/escalations/output-gate rejections + 5% random sample → `eval_candidates`; shadow-replay harness (replay last-7-days traffic offline, diff decisions) | A 👎 appears in the review digest ≤1 min after tap; a prompt-change PR without a shadow-replay report fails CI |
| 5.10 | Degradation ladder (TRD §9): OpenRouter failover → LLM-free **menu mode** (list picker + deterministic tools); keyword pre-router; Mongo fallback queue; per-vendor circuit breakers; chaos drill script in `ops/` | Staging chaos drill: each dependency killed once, bookings still completable in menu mode, zero dropped messages |

**Exit:** M1.3 — full P0 acceptance in UAT; F1 ≥90%; hallucination = 0.

### Week 6 — Production + pilot onboarding (Milestone M1.4)

| # | Task | Definition of done |
|---|------|--------------------|
| 6.1 | Prod deploy: VPS + Docker Compose, Caddy TLS, Atlas M10 ap-south-1, Upstash Redis; Sentry; UptimeRobot on health endpoint | Deploy runbook = `git pull && docker compose up -d --build`; documented |
| 6.2 | Backup/restore drill: Atlas continuous backup verified, restore to staging executed once, timed | RTO ≤15 min demonstrated, logged in `ops/restore_runbook.md` |
| 6.3 | Onboard 5 LOI clinics via `seed_tenant.py` + KB YAML sheet: KB, schedules, holiday calendar (Odisha set), location pin + landmark, staff training | Each onboarding ≤1 day wall clock; checklist per clinic |
| 6.4 | Transcript review tooling: daily digest of 100% pilot conversations, one-tap "add to eval set" flagging | Taxonomy/KB misses fixed same-day during pilot week 1 |
| 6.5 | KB auto-draft (F-23) v0: Google Business Profile + website scrape (+ OCR of price-list photo) → draft KB YAML → owner approves line-by-line during onboarding | Clinic #5 onboarded in ≤1 hour using the auto-draft |

**Exit:** M1.4 — 5 clinics live; first organic booking with zero human help.

---

## 2. Phase 2 Engineering — Voice (Weeks 7–12)

Architecture rule: voice is **a new channel adapter, not a new agent**. `channels/voice/` produces the same normalized inbound events the WhatsApp gateway does; the LangGraph core is untouched except for a `channel` hint (shorter responses, no rich menus on voice).

**Weeks 7–8 (M2.1):**
- STT bake-off harness: run Phase-0 corpus (8kHz phone audio, Hindi + Odia) through Sarvam / Deepgram / Google → WER, latency-to-first-partial, ₹/min table → finalize ADR-05 *on data*.
- Exotel number + media-stream WebSocket: call session ↔ conversation mapping, streaming STT partials into the graph, sentence-chunked TTS out, barge-in (kill TTS on caller speech).
- Latency budget instrumented per hop (STT ≤300ms partial, LLM first token ≤700ms, TTS first audio ≤400ms); filler acknowledgment ("जी, एक second…") auto-injected when budget slips.
- **DoD:** live call → booking loop, first audio response ≤2.0s happy path, per-hop latency dashboard.

**Weeks 9–10 (M2.2):**
- Repeat/clarify flows; DTMF fallback ("press 1") for very noisy calls; warm transfer to owner phone on handoff; voicemail-to-task when unreachable.
- Consent line at call start (per Q3 counsel answer); recordings stored in audit trail, media auto-purge at 30d.
- **DoD:** 20 scripted calls with native Hindi + Odia speakers on real phones with ambient noise → task success ≥80%, wrong-fact utterances = 0.

**Weeks 11–12 (M2.3):**
- Enable for 2 pilot clinics as **forward-on-busy/no-answer** only (lower risk than full takeover).
- Per-minute COGS telemetry per tenant wired into the daily cost report; margin check vs Pro plan.
- **DoD:** 100 real calls, containment ≥50%, COGS ≤₹4/min actual — else park voice per gate G2.

---

## 3. Phase 3 Engineering — Monetization & Scale (Months 4–6)

Build order is deliberate: **the thing that sells the renewal ships first.**

1. **Weekly ROI summary (F-13):** worker computes recovered bookings (after-hours + busy-line + previously-missed numbers), revenue estimate, containment; sends owner WhatsApp template. *Ships before any billing code — it is the retention product.*
2. **Billing:** Razorpay subscriptions + UPI Autopay mandate lifecycle (create on pilot start, activate on day 30, dunning on failure); GST tax invoice generation (F-17: Xolver GSTIN, SAC, 18%, clinic GSTIN) auto-delivered monthly. Live before the first paid invoice.
3. **Reminders (F-11)** if not shipped in pilot; reschedule-from-reminder deep flow.
4. **Payments (F-12):** `payment_link_create` tool + Razorpay webhook reconciliation + max-2 nudge sequence (opt-in gated).
5. **Missed-call bridge (F-16):** Exotel missed-call number → `missed_call_bridge` utility template → conversation opens. Doubles as the demo closer for city-2 sales.
6. **No-show recovery + waitlist + cancellation auto-backfill (F-15/F-22):** cancel event → instant slot offer to waitlisted patients, first tap wins; cancelled slots refill themselves.
7. **Onboarding efficiency:** KB import sheet + self-serve-ish KB editor for owners (US-9) → white-glove ≤3h/clinic.
8. **Hardening:** on-call basics (Sentry alert → phone), quarterly restore + DPDP drills, monthly Meta scope self-audit tooling (random 50-transcript sampler with taxonomy diff report — automate the compliance calendar).
9. **Experience pack (runs alongside 3–6, not after):** WhatsApp Flows booking form (F-19) A/B'd against the list picker per language cohort; patient memory + one-tap rebook (F-20, `contacts.profile`); classifier fine-tune once the labeled corpus passes 10K utterances (TRD §10) — cost per classification drops as quality rises.

**Scale posture check at 25 tenants:** still one VPS (peak <5 req/s). Only permitted infra change: split worker container from API container if reminder bursts delay inbound p95. No k8s, no microservices, no vector DB.

---

## 4. Cross-Cutting Engineering Standards (all phases)

| Area | Standard |
|------|----------|
| CI pipeline | ruff + mypy → unit tests → tenant-isolation suite → eval gate (intent F1, scope accuracy, hallucination=0) → image build. Nightly: 500-race test + full eval on all 4 languages. |
| Deploys | Trunk-based; deploy = tagged image; prompt/taxonomy changes carry an eval report link in the PR. Rollback = redeploy previous tag (<5 min). |
| Observability | Structured JSON logs with `tenant_id`/`conversation_id` on every line; per-node latency + token counters; Sentry; daily per-tenant cost report (launch blocker). |
| Data | India region only; phone numbers CSFLE-encrypted; audit append-only, 90d TTL default; media purged at 30d; erasure pipeline ≤7d SLA. |
| Testing pyramid | Unit (tools, resolver, window tracker) → integration (webhook→reply against mocked Meta) → eval suite (the real quality gate) → scripted human UAT per milestone. |
| Resilience | Degradation ladder per TRD §9: per-vendor circuit breakers; menu mode (LLM-free booking) proven in a staging chaos drill before pilot; a message is never dropped (Mongo fallback queue when Redis is down). |
| Quality flywheel | Shadow replay of last-7-days traffic required on every prompt/taxonomy PR (CI-enforced); nightly LLM-judge trend (groundedness, register, language-match); weekly labeling ritual grows the eval set ≥50 utterances/wk during pilot (TRD §10). |
| Definition of done (global) | Code + tests + eval pass + audit coverage + cost metered + doc line in the relevant runbook. Anything user-facing exists in all 4 languages or doesn't ship. |

## 5. Dependency-Critical Path (what can stall the build)

```
Wk1: Meta Business verification + BSP number  ──(1–6 wks)──►  needed by Wk3 test number
Wk2: Template pack approval (8 templates × 4 langs)  ──(days–2wks)──►  needed by Wk5 alerts
Wk2: DPDP notice counsel sign-off  ──►  blocks first pilot message (Wk6)
Wk2: Q1 Meta/BSP rate card verification  ──►  blocks pricing lock, not code
Phase 0 voice corpus (50 calls)  ──►  blocks Wk7 STT bake-off
Q3 call-recording counsel answer  ──►  blocks Wk10 recording feature, not plumbing
```

Rule: anything on this list gets started the week it appears here, tracked in the weekly ritual, and has a fallback (e.g., second BSP sandbox number for Wk3 if verification drags).
