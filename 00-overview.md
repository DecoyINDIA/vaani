# Project Vaani — Planning Pack Overview

**Product:** Vernacular AI front-desk agent (WhatsApp + voice) for Indian appointment-driven SMBs. v1 vertical: clinics.
**Date:** 07 Jul 2026 (v2.0 upgrade: 18 Jul 2026) | **Owner:** Subham Jena (Xolver)

## Documents

| Doc | Contents |
|-----|----------|
| 01-PRD.md | Problem, personas, goals/non-goals, user stories, P0/P1/P2 requirements with acceptance criteria, metrics, open questions |
| 02-TRD.md | Architecture, 7 ADRs, data model, agent design (closed intent taxonomy + dual scope gates), APIs, NFRs, cost model |
| 03-build-plan.md | Phases 0–3 with weekly milestones, binary entry/exit gates, kill/pivot criteria, budget (~₹2.5–3.5L to Month-6 decision) |
| 04-gtm-pricing.md | Positioning, pricing (₹2,999/₹6,999 + outcome overage), ICP, channels, validation script, funnel targets |
| 05-risk-compliance.md | 10-item risk register, Meta 2026 WhatsApp policy controls, DPDP processor plan, legal items, compliance calendar |
| 06-engineering-plan.md | End-to-end engineering execution: repo/monorepo layout, week-by-week tasks with definitions of done, walking-skeleton build order, voice channel plan, Phase-3 build order, CI/eval gates, dependency critical path |
| 07-tdd-loops.md | TDD execution discipline: the engineering plan reorganized into strict build→test→pass loops (L0–L16 + Phase-3 micro-loops). Tests written first (evals count as tests), a loop closes only on a cumulative green bar, next loop blocked until then |
| 08-user-flows.md | End-to-end user flows at message level: 10 design principles (Anthropic-grade honesty/refusal/attention rules), 17 patient flows with actual copy, 8 owner flows, staff flow, latency choreography, flow→requirement→loop traceability |

## The 5 decisions already made (challenge now or accept)

1. **Clinics only for v1.** One vertical, one city, 25 references before expansion.
2. **WhatsApp before voice.** Voice is the differentiator but WhatsApp proves value in 4 weeks; voice has a hard kill-switch if COGS >₹5/min.
3. **Compliance in code, not prompts.** Closed intent set + dual gates = Meta policy safety and the anti-hallucination guarantee. This constrains the product deliberately.
4. **Outcome-linked pricing.** Base subscription + per-booking/per-minute overage. Protects margin; aligns to value.
5. **No code before 5 signed LOIs.** Phase 0 gate is binary.

## Blocking items this week (Week 1)

1. Book 20 clinic interviews (script: GTM §5). 
2. Kick off Meta Business verification + BSP number (1–6 wk lead time).
3. Verify Meta's per-message pricing (July 2025 regime — service replies free) + BSP markup → lock margin math (PRD Q1).
4. Send DPDP notice + DPA template to counsel.
5. Submit 7 WhatsApp templates for approval.

## Top 3 risks to watch (full register in doc 05)

- **R2 Vernacular accuracy** (Exp 16): decided by data (STT bake-off, eval suite), not optimism.
- **R4 SMB churn** (Exp 16): countered by ROI-visible features (weekly summary, payments), not engagement tricks.
- **R6 Founder bandwidth** (Exp 16): binary gates exist so scope gets cut, not timelines stretched.

## India-market hardening (v1.1 changes)

- **Money:** all prices quoted +18% GST with auto-issued tax invoices (F-17); UPI Autopay under the ₹15K no-AFA limit; Meta cost model updated to the July-2025 per-message regime (service replies free → Starter margin improves to ~60–82%).
- **Behavior:** missed-call-to-WhatsApp bridge (F-16) — converts India's missed-call habit into bookings and doubles as the sales demo closer.
- **Language:** "kal/parso" relative-date confirmation rule enforced in the booking tool contract; colloquial time parsing; respectful-register default; landmark-based directions via location pin.
- **Calendar:** per-tenant festival/holiday calendar blocks slot generation on closed days (seeded with Odisha festivals at onboarding).
- **Expansion:** language–city coupling rule in GTM — city 3 must need zero new languages, or budget a full language-pack cycle first.
- **Compliance:** DPDP Rules 2025 phase-in mapped to the compliance calendar; Telemedicine Guidelines perimeter stated; TRAI DLT flagged for any future SMS; GST/SAC registration item added.

## Top-1% upgrade layer (v2.0 changes)

v1.1 was a plan that works; v2.0 raises the bar to top-1%. Ten bets, all slotted into existing phases — **no timeline change, no new gates weakened**:

1. **Booking in taps, not typing** — WhatsApp list-message slot picker + reply buttons (F-18, now P0); Flows form A/B later (F-19). Booking conversion target 60% → 70%.
2. **Speed as product** — p50 ≤3s; mark-as-read + typing indicator ≤1s. Perceived latency budgeted like COGS.
3. **Patient memory** — returning patients greeted by name; one-tap rebook (F-20). Repeat booking in ≤2 taps.
4. **Revenue autopilot** — cancellation auto-backfill from waitlist (F-22): cancelled slots refill themselves. No-show risk scoring parked in P2.
5. **In-chat CSAT** (F-21) — 1-tap 👍/👎 after resolution; new goal G6 ≥4.3/5; every 👎 becomes an eval candidate.
6. **1-hour onboarding** — KB auto-draft from Google Business Profile + website (F-23); new activation goal G7: first organic booking ≤72h of go-live, 100% of clinics.
7. **Degradation ladder** (TRD §9) — LLM down → deterministic menu-mode booking still works; a patient never gets silence. Chaos drill before pilot.
8. **Quality flywheel** (TRD §10) — escalations/👎/gate-rejections auto-become eval candidates; shadow replay of 7 days of production traffic gates every prompt change; consented corpus → classifier fine-tune at 10K utterances. This is the compounding moat vs copycats (R7).
9. **Voice bake-off widened** (ADR-05) — realtime speech-to-speech models compete against the cascaded STT→LLM→TTS pipeline; cascade becomes fallback if duplex wins on latency + Indic accuracy at ≤₹4/min.
10. **PMF instrumentation + product-led growth** — Sean Ellis test at day 45; "Powered by Vaani" loop on patient messages; referral CTA inside the weekly ROI summary owners already screenshot into their WhatsApp groups (GTM).

**North-star metric (new, PRD §4): confirmed bookings handled end-to-end by Vaani per tenant per week.** Every feature must name its input to this number or it doesn't ship.
