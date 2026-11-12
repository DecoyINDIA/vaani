# Project Vaani — Planning Pack Overview

**Product:** Vernacular AI agents (WhatsApp + voice) that run the front office of Indian small and medium businesses. Two agents: a **Front-desk agent** (receptionist + follow-up/recall in one) and a **Reporting agent** (the owner's daily brief).
**Market:** SMBs of any trade, starting in **Bhubaneswar**. No single industry is assumed; each business is described to the agent by a per-tenant business profile set at onboarding.
**Date:** 07 Jul 2026 (v2.0 upgrade: 18 Jul 2026; SMB reframe: 11 Nov 2026) | **Owner:** Subham Jena (Xolver)

> **Status of this reframe.** The industry-neutral wording, intents and per-tenant `business_profile` are implemented in code. The daily brief is **built and tested offline** (`app/workers/daily_brief.py`) but not live: its WhatsApp template is a draft that still needs wording review and Meta approval. Recall of past customers is **planned**, not built; the code has reminders, no-show recovery and slot backfill today. Pricing is **under review** because the current per-account revenue does not cover the cost of acquiring and serving a customer (see [04-gtm-pricing.md](04-gtm-pricing.md)). The earlier "clinics only for v1" decision is withdrawn.

## Documents

| Doc | Contents |
|-----|----------|
| 01-PRD.md | Problem, personas, goals/non-goals, user stories, P0/P1/P2 requirements with acceptance criteria, metrics, open questions |
| 02-TRD.md | Architecture, 7 ADRs, data model, agent design (closed intent taxonomy + dual scope gates), APIs, NFRs, cost model |
| 03-build-plan.md | Phases 0–3 with weekly milestones, binary entry/exit gates, kill/pivot criteria, budget (~₹2.5–3.5L to Month-6 decision) |
| 04-gtm-pricing.md | Positioning, pricing, ICP, channels, validation script, funnel targets |
| 05-risk-compliance.md | Risk register, Meta 2026 WhatsApp policy controls, DPDP processor plan, legal items, compliance calendar |
| 06-engineering-plan.md | Engineering execution: repo layout, week-by-week tasks with definitions of done, build order, CI/eval gates |
| 07-tdd-loops.md | TDD execution discipline: the engineering plan as strict build→test→pass loops |
| 08-user-flows.md | Message-level user flows with actual copy, design principles, flow→requirement→loop traceability |

## Product shape

| Agent | Job | Status |
|-------|-----|--------|
| **Front-desk agent** | Answers calls and WhatsApp in the customer's language, answers questions from approved facts, books/moves/cancels appointments, collects payment links, hands off to staff. Also **follows up**: confirmations, reminders, no-show recovery, cancellation backfill, and recall of past customers. | Reception, booking, reminders, backfill: implemented. Recall campaigns: planned (marketing-category templates are policy-gated — see 05). |
| **Reporting agent** | Sends the owner a short **daily brief** on WhatsApp: bookings, revenue recovered, missed contacts, open escalations, what needs a decision today. | Daily brief: implemented, offline-tested, awaiting template approval. Weekly summary: implemented. |

CRM, accounting and sales tooling are **not** in scope for v1. They are reached through integrations or later agents once the two above have paying references.

## Decisions already made (challenge now or accept)

1. **Any appointment-driven SMB, Bhubaneswar first.** One city, many trades; 25 paying references before leaving the city. Fit test: does the business take bookings or enquiries by call/WhatsApp? Shops and wholesalers that need quotes or orders are a different capability and are not v1.
2. **Configured, not hard-coded.** Business type, what the business calls its customers and staff, and which advice topics must be refused live on the tenant record (`business_profile`), not in prompts or templates.
3. **WhatsApp before voice.** Voice is the differentiator but WhatsApp proves value in 4 weeks; voice has a hard kill-switch if COGS >₹5/min.
4. **Compliance in code, not prompts.** Closed intent set + dual gates = Meta policy safety and the anti-hallucination guarantee. This constrains the product deliberately.
5. **Outcome-linked pricing.** Base subscription + per-booking/per-minute overage. Protects margin; aligns to value. Price points under review.
6. **No code before 5 signed LOIs.** Phase 0 gate is binary.

## Blocking items this week (Week 1)

1. Book 20 owner interviews across at least 4 trades (script: GTM §5).
2. Kick off Meta Business verification + BSP number (1–6 wk lead time).
3. Verify Meta's per-message pricing (July 2025 regime — service replies free) + BSP markup → lock margin math (PRD Q1).
4. Send DPDP notice + DPA template to counsel.
5. Submit WhatsApp templates for approval.
6. Decide pricing for the combined Front-desk + Reporting bundle before the first interview.

## Top 3 risks to watch (full register in doc 05)

- **R2 Vernacular accuracy** (Exp 16): decided by data (STT bake-off, eval suite), not optimism.
- **R4 SMB churn** (Exp 16): countered by ROI-visible features (daily brief, payments), not engagement tricks.
- **R6 Founder bandwidth** (Exp 16): binary gates exist so scope gets cut, not timelines stretched.
- **R11 Breadth dilutes quality (new):** many trades means many vocabularies. Mitigation: onboarding captures the profile and an eval set per trade; add a trade to the supported list only after its eval passes.

## India-market hardening (v1.1 changes)

- **Money:** all prices quoted +18% GST with auto-issued tax invoices (F-17); UPI Autopay under the ₹15K no-AFA limit; Meta cost model on the July-2025 per-message regime (service replies free).
- **Behavior:** missed-call-to-WhatsApp bridge (F-16) — converts India's missed-call habit into bookings and doubles as the sales demo closer.
- **Language:** "kal/parso" relative-date confirmation rule enforced in the booking tool contract; colloquial time parsing; respectful-register default; landmark-based directions via location pin.
- **Calendar:** per-tenant festival/holiday calendar blocks slot generation on closed days (seeded with Odisha festivals at onboarding).
- **Expansion:** language–city coupling rule in GTM — city 2 must need zero new languages, or budget a full language-pack cycle first.
- **Compliance:** DPDP Rules 2025 phase-in mapped to the compliance calendar; regulated-advice perimeter (health, legal, financial) handled by the per-tenant restricted-topics list; TRAI DLT flagged for any future SMS; GST/SAC registration item added.

## Top-1% upgrade layer (v2.0 changes)

Ten bets, all slotted into existing phases:

1. **Booking in taps, not typing** — WhatsApp list-message slot picker + reply buttons (F-18, P0); Flows form A/B later (F-19). Booking conversion target 60% → 70%.
2. **Speed as product** — p50 ≤3s; mark-as-read + typing indicator ≤1s.
3. **Customer memory** — returning customers greeted by name; one-tap rebook (F-20).
4. **Revenue autopilot** — cancellation auto-backfill from waitlist (F-22). No-show risk scoring parked in P2.
5. **In-chat CSAT** (F-21) — 1-tap 👍/👎 after resolution; goal G6 ≥4.3/5; every 👎 becomes an eval candidate.
6. **1-hour onboarding** — KB auto-draft from Google Business Profile + website (F-23); activation goal G7: first organic booking ≤72h of go-live, 100% of businesses.
7. **Degradation ladder** (TRD §9) — LLM down → deterministic menu-mode booking still works; a customer never gets silence.
8. **Quality flywheel** (TRD §10) — escalations/👎/gate-rejections auto-become eval candidates; shadow replay of 7 days of production traffic gates every prompt change.
9. **Voice bake-off widened** (ADR-05) — realtime speech-to-speech models compete against the cascaded STT→LLM→TTS pipeline.
10. **PMF instrumentation + product-led growth** — Sean Ellis test at day 45; "Powered by Vaani" loop on customer messages; referral CTA inside the owner's brief.

**North-star metric (PRD §4): confirmed bookings handled end-to-end by Vaani per tenant per week.** Every feature must name its input to this number or it doesn't ship.
