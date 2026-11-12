# 01 — PROJECT INTELLIGENCE

**Repository:** `github.com/DecoyINDIA/vaani` · **Reviewed commit:** `847d5f5` (9 Nov 2026) · **Review date:** 11 Nov 2026
**Method:** read-only clone; code read along execution paths (webhook → queue → agent graph → booking → send; owner API → dashboard). Nothing was run, installed, or modified. Statements below are tagged **[FACT]** (seen in code), **[CLAIM]** (stated in repo docs, not independently verified), **[HYPOTHESIS]**, or **[UNKNOWN]**.

---

## 1. What it is

**[FACT]** Vaani is a multi-tenant "AI front desk" for appointment-driven Indian small businesses, v1 vertical clinics (dental/general). Patients talk to it on **WhatsApp** (and, in code, by **phone**); it answers FAQs from an approved knowledge base, books/reschedules/cancels appointments against a slot calendar, sends reminders, and hands off to human staff. Owners/staff use a small web dashboard. Owner: Subham Jena (Xolver). Licence: proprietary.

**Problem solved:** small clinics lose bookings to missed calls and slow WhatsApp replies; a receptionist costs ₹12–18K/month and works business hours only (`04-gtm-pricing.md`).

**Intended users:** (a) patients, in Hindi / Hinglish / Odia / English; (b) clinic owner and front-desk staff; (c) the operator (Xolver) who onboards tenants by CLI.

## 2. How it works end to end (verified in code)

```
Meta webhook  POST /webhooks/meta            app/gateway/meta.py
  └ HMAC verify → resolve tenant by display number → erasure-suppression check
  └ durable insert into Mongo `messages` (queue of record) → XADD Redis stream (wake-up only)
Worker        python -m app.workers.inbound  app/workers/inbound.py
  └ lease the message → upsert contact, find/create conversation
  └ if conversation.state == "human": store only, bot stays silent
  └ STOP/START opt-out keywords
  └ interactive reply? → deterministic booking state machine (slot picker → Confirm button → booking)
  └ else LangGraph: lang_detect → intent (LLM, closed 18-label set) → scope_gate
        → tool_router (kb_search | slots_get) → responder (LLM, grounded) → output_gate → [handoff]
  └ book/reschedule → WhatsApp list picker; cancel/status → handled in worker code
  └ send via app/channels/whatsapp.py (24h-window check, outbound-intent ledger, audit)
Same worker process also runs a 15-minute scheduler: slot expansion, reminders (24h/2h),
escalation SLAs, monthly invoices, weekly owner summary, stale-send reconciliation.
Owner API    /api/auth/*, /api/*             app/owner_api/   (JWT, tenant from token)
Dashboard    dashboard/src/App.tsx           single-file React SPA served by FastAPI
Voice        /webhooks/exotel + WebSocket    app/gateway/exotel.py, app/channels/voice/*
Payments     /webhooks/razorpay              app/gateway/razorpay.py, app/billing/*
```

**Stack [FACT]:** Python 3.12, FastAPI, Motor/MongoDB (Atlas Search + vector for KB), Redis Streams, LangGraph, OpenRouter (LLM + embeddings), lingua; React 18 + Vite + Tailwind; Docker Compose on a single VPS; GitHub Actions CI publishing to GHCR. Providers: Meta WhatsApp Cloud API, Exotel (telephony), Sarvam (STT/TTS), Razorpay.

**Size [FACT]:** ~9.3K lines of app code (43 non-empty Python files), ~8K lines of tests (37 files), 1.1K-line CI workflow, 132-line dashboard, ~2.5K lines of planning docs. 91 commits by one author; **80 of them between 7 and 9 Nov 2026**, in a strict "fix → docs: record evidence" rhythm that indicates agent-driven remediation.

## 3. Technical maturity

| Area | State | Basis |
|---|---|---|
| Tenant isolation at data layer | Solid | `TenantScoped` accessor injects `tenant_id`; CI grep forbids raw `db[...]` outside `app/models/` [FACT] |
| Booking integrity | Solid design | hold→confirm with operation-owned holds, Mongo transactions, idempotent `request_id` (`app/booking/engine.py`) [FACT]; 500-claim race test [CLAIM, CI] |
| Durable inbound/outbound | Solid design | Mongo as queue of record, leases, outbound-intent ledger that refuses to blind-retry ambiguous sends [FACT] |
| Auth | Adequate for pilot | purpose-typed JWTs, hashed single-use magic tokens, rotating refresh sessions, production-secret guard [FACT] |
| WhatsApp booking journey | Works on mocks, thin | one practitioner, one service, date-only, English-only flow copy [FACT] |
| Agent quality | **Unproven** | every test and the 25-case eval run on a keyword-matching mock LLM (`app/agent/llm.py:13`) [FACT] |
| Dashboard | **Not operable** | no patient names, no appointment times, timestamp literally `now` [FACT] |
| Voice | Protocol-level only | never exercised against Exotel/Sarvam; streaming STT raises `NotImplementedError` [FACT] |
| Billing | Coded, untested live | plans, GST invoice rendering, Razorpay lifecycle [FACT]; no sandbox run [CLAIM] |
| Live operation | **None** | repo's own ledger: "staging deployment and live provider credentials pending" [CLAIM, consistent with code] |

**Overall:** a well-engineered pre-pilot backend whose safety scaffolding is ahead of its product surface. It has never handled a real patient message.

## 4. Implemented vs planned

**Implemented [FACT]:** WhatsApp ingress/egress, intent+scope gates, grounded FAQ, slot generation, booking create/move/cancel, reminders, handoff with staff alert + SLA, opt-out, owner auth + inbox/takeover/reply/return, KB upsert, DPDP erasure tooling, migration/restore tooling, invoice + usage metering, Exotel/Sarvam protocol adapters.

**Planned in docs, absent or stubbed in code [FACT]:**
- Waitlist backfill (F-22): nothing ever inserts into `waitlist`; "offer" is only an audit row (`booking_cancel.py:62`).
- In-chat CSAT (F-21): no collection path; dashboard reads a field nothing writes.
- Returning-patient one-tap rebook (F-20): prompt text only; `profile.last_service` is never written.
- KB auto-draft from Google Business Profile (F-23), WhatsApp Flows, mark-as-read/typing indicator, degraded "menu mode", quality flywheel/shadow replay, "Powered by Vaani" loop: none present.
- Time-of-day understanding: `parse_colloquial_time` exists but is never called.
- Self-serve onboarding, holiday/schedule editing in the dashboard: CLI only (`ops/onboard_tenant.py`).

## 5. Dependencies and constraints

- **Meta** WABA verification, per-tenant sender + token, approved utility templates (5 in code contracts). Tokens are read from **environment variables named in the tenant document** (`whatsapp.py:100-116`) → adding a tenant means editing env and restarting.
- **MongoDB Atlas** specifically (transactions need a replica set; KB search needs Atlas Search/Vector).
- **OpenRouter** for both LLM calls per message and embeddings; no model is pinned in the repo (`LLM_MODEL_*` empty in `.env.example`).
- **Startup requires every provider** — Exotel, Sarvam, Razorpay, GSTIN — even for a WhatsApp-only pilot (`config.py:92-112`).
- **Regulatory:** DPDP Act processor duties, Meta's business-AI policy (general-purpose assistants barred from the Business API since 15 Jan 2026; business-specific bots allowed), Telemedicine perimeter (no medical advice — enforced by graph topology).
- **Human:** single founder; 17 external prerequisites all "Pending" in the repo's own register.

## 6. Business model (from repo docs) [CLAIM]

Subscription + outcome overage, +18% GST, UPI Autopay: **Starter ₹2,999/mo** (WhatsApp, 1,000 conversations, 50 bookings, ₹49/extra booking, ₹2/extra conversation); **Pro ₹6,999/mo** (adds voice 300 min, ₹4/extra min); custom setup ₹25K+. Beachhead Bhubaneswar → Cuttack → a Hindi-belt metro. Founder-led sales; target 25 paying clinics by month 6; break-even at 15–20 Starter customers. Gate G0 requires **5 signed LOIs before writing code** — **[UNKNOWN]** whether any exist; nothing in the repo evidences one.

## 7. Competitive advantage

**Real, in code:** compliance-by-topology (medical/out-of-scope intents cannot reach the LLM), numeric grounding gate, honest delivery ledger, DPDP erasure with a replayable suppression ledger, race-safe booking. These are harder to copy than a prompt.

**Claimed but not yet real:** "vernacular accuracy proven on real calls" (no real-model eval exists), voice, 24-hour onboarding.

**Market reality [external, vendor-sourced, unverified]:** many small entrants already sell clinic AI receptionists in India at ₹999–₹11,999/mo (CareVoice, CatchAI, AiSensy agent library, Curastax). Sarvam sells a managed Indic voice-agent platform including telephony from about ₹3/min. Distribution and proof, not architecture, will decide this.

## 8. Strongest realistic version

A WhatsApp-first front desk that a 1–3 doctor clinic can be live on in a day, that books in two taps in the patient's language, that staff can actually run from a phone-sized dashboard (names, times, today's list), and that sends the owner a truthful weekly number: bookings handled without staff. Voice arrives later as a bought component, not a built one. The compliance and durability core already in the repo becomes the reason an owner — and Meta — trusts it.

## 9. Open unknowns requiring the owner

1. Do signed LOIs / interview results exist? (Gate G0.)
2. Is WABA verification submitted? Which BSP, or direct Cloud API?
3. Which LLM models are intended in production, and has anyone run the agent against a real model even once?
4. Is the 50-bookings Starter cap intentional? (The pricing memo models 350 bookings/month on Starter.)
5. Is there any production or staging data, or is the migration tooling for a database that does not yet exist?
