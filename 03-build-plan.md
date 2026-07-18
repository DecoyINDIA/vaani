# Phased Build Plan — Project Vaani

**Version:** 2.0 | **Date:** 18 Jul 2026 | Assumes: Subham + Antigravity/Claude Code execution model, 1 part-time contractor for voice phase if needed. Weeks are calendar weeks from kickoff (Week 1 = 14 Jul 2026).

**Rule:** every phase has an entry gate and an exit gate. No phase starts before its entry gate passes. Gates are binary — no "mostly done."

---

## Phase 0 — Validation & Groundwork (Weeks 1–2)

**Goal:** prove demand before building; unblock long-lead-time dependencies.

| # | Task | Output | Days |
|---|------|--------|------|
| 0.1 | Interview 20 clinic owners (Bhubaneswar; script in GTM doc §5) | Filled interview sheet: missed calls/day, current handling, price reaction | 6 |
| 0.2 | Collect 5 pre-commitments (signed 1-page pilot LOI: 30 days free → ₹2,999/mo auto-start, cancel anytime) | 5 signed LOIs | with 0.1 |
| 0.3 | Start Meta Business verification + BSP number provisioning (1–6 wk lead time) | Verified WABA, number live | 1 (start) |
| 0.4 | Submit WhatsApp template pack for approval (7 templates, 4 languages) | Approved templates | 1 (start) |
| 0.5 | DPDP notice + consent copy drafted; counsel review booked | Reviewed notice v1 | 2 |
| 0.6 | Resolve Q1 (BSP/Meta conversation pricing) → lock pricing | Pricing memo | 1 |
| 0.7 | Record 50 sample clinic calls / collect voice notes (with consent) for STT bake-off corpus | Labeled audio corpus | ongoing |

**Exit gate G0:** ≥5 signed LOIs AND WABA verification submitted AND pricing memo confirms >60% Starter margin. **If <5 LOIs: stop. Re-vertical (salons) or re-price. Do not write product code.**

---

## Phase 1 — WhatsApp Agent MVP (Weeks 3–6)

**Goal:** live product answering real patients for 5 pilot clinics.

### Week 3 — Skeleton
- Repo, CI (lint, tests, eval gate), Docker Compose, environments (dev/prod).
- FastAPI gateway: Meta webhook (verify, dedupe, ack <5s), Redis Streams queue, worker scaffold.
- Data model migrations for all P0 collections; tenant seed script.
- LangGraph skeleton: lang_detect → intent_classifier → scope_gate → responder(stub) → output gate(stub).
- **Milestone M1.1:** echo-with-intent bot live on test number; intent classifier ≥85% F1 on seed eval set (150 utterances).

### Week 4 — Booking engine + KB
- Slots model + atomic hold/confirm; practitioner schedules; booking create/move/cancel tools.
- KB collection + Atlas Search retrieval; KB-grounded responder with citation requirement; output scope gate live.
- Templated flows: medical refusal, out-of-scope, escalation copy (4 languages).
- Interactive booking UX (F-18): list-message slot picker (top 8 + "more"), reply-button Confirm/Change/Cancel, free-text fallback; per-step conversion instrumented.
- **Milestone M1.2:** end-to-end booking on test number in Hindi + Hinglish **in ≤3 taps after intent**; 500-concurrent race test passes with 0 double-bookings.

### Week 5 — Handoff + dashboard
- Handoff state machine + staff WhatsApp alerts; escalation inbox.
- Dashboard v1: conversations, transcripts, bookings calendar, escalations, settings, KB editor (Xolver-facing initially).
- Audit log + usage metering + daily cost report.
- Consent/notice message on first contact; contact consent state.
- CSAT capture (F-21) + quality flywheel v0: 👎/escalations/gate-rejections auto-queued as eval candidates; weekly labeling ritual on the calendar; degradation-ladder chaos drill in staging (TRD §9).
- **Milestone M1.3:** full P0 acceptance checklist passes in UAT with 2 non-technical testers; eval set grown to 300 utterances, intent F1 ≥90%, factual-claim hallucination = 0.

### Week 6 — Pilot onboarding
- KB auto-draft v0 (F-23): Google Business Profile + website scrape → draft KB sheet, reviewed with the owner during onboarding (target: clinic #5 onboarded in ≤1 hour).
- White-glove onboard 5 LOI clinics: KB filled, schedules loaded, holiday calendar seeded (national + Odisha festivals — Raja, Rath Yatra, Nuakhai — plus clinic-specific closures), location pin + landmark line captured, staff trained (30-min session each), number forwarded/publicized on their profiles.
- Daily monitoring ritual: review 100% of transcripts for week 1 of each pilot; fix taxonomy/KB gaps same-day.
- **Milestone M1.4:** 5 clinics live; first organic booking completed without human help.

**Exit gate G1 (measured over pilot weeks 6–8):** containment ≥60%, booking conversion ≥50%, hallucination incidents = 0, at least 3 of 5 owners say they'd pay when trial ends (verbal). **If containment <45% after 2 weeks of tuning: freeze features, fix agent quality only.**
*Top-1% bar (targets, not kill thresholds — gates stay as written):* containment ≥70%, conversion ≥70% (interactive picker), CSAT ≥4.3, every clinic's first organic booking ≤72h of go-live (G7).

---

## Phase 2 — Voice Layer (Weeks 7–12, overlaps pilot ops)

**Goal:** answer the clinic's phone line; same agent core.

### Weeks 7–8 — Bake-off + plumbing
- STT bake-off (Sarvam vs Deepgram vs Google) on Phase-0 corpus: WER per language, latency, cost → ADR-05 finalized on data.
- Exotel number + SIP/media-stream integration; barge-in handling; call session ↔ conversation mapping.
- **Milestone M2.1:** live call → streaming transcript → agent → TTS reply loop working; first-response ≤2.0s on happy path.

### Weeks 9–10 — Voice UX hardening
- Filler/ack strategy for latency spikes; repeat/clarify flows; DTMF fallback ("press 1") for very noisy calls.
- Warm transfer to owner phone on handoff; voicemail-to-task when owner unreachable.
- Call recording + consent line at call start (per Q3 legal answer); recordings in audit trail.
- **Milestone M2.2:** 20 scripted test calls (native Hindi + Odia speakers, real phones, ambient noise) — task success ≥80%, zero wrong-fact utterances.

### Weeks 11–12 — Voice pilot
- Enable voice for 2 of 5 pilot clinics (call forwarding on busy/no-answer first — lower risk than full takeover).
- Per-minute cost telemetry per tenant; margin check against Pro plan.
- **Milestone M2.3:** 100 real calls handled; containment ≥50% on voice; owner qualitative sign-off.

**Exit gate G2:** voice COGS ≤ ₹4/min actual, voice containment ≥50%, no compliance/legal open items. **If voice COGS >₹5/min or containment <35%: ship WhatsApp-only commercially, park voice 1 quarter. Voice is a differentiator, not a dependency.**

---

## Phase 3 — Monetization & Scale to 25 (Months 4–6)

**Goal:** convert pilots, reach 25 paying customers, prove retention.

| Workstream | Contents |
|------------|----------|
| Convert | Trial→paid flow (Razorpay subscriptions/UPI Autopay); GST tax invoicing live before first paid invoice (F-17); pilot conversion target ≥60%. |
| Retention features | Reminders (F-11) if not already shipped, payments (F-12), weekly ROI summary (F-13), no-show recovery + cancellation auto-backfill (F-15/F-22 — cancelled slots refill themselves from the waitlist), missed-call-to-WhatsApp bridge (F-16 — doubles as the demo closer for city-2 sales). Ship ROI summary FIRST — it sells the renewal. |
| Experience pack | WhatsApp Flows booking form (F-19) A/B'd against the list picker per language cohort; patient memory + one-tap rebook (F-20); classifier fine-tune once the labeled corpus passes 10K utterances (TRD §10). |
| Onboarding efficiency | Reduce white-glove onboarding to ≤3 hours/clinic (templates, KB import sheet); prerequisite for scaling without hiring. |
| Sales | 3 case studies with hard numbers; referral offer (1 month free per referred clinic); expand to 2nd city via dental association/WhatsApp groups (GTM doc). |
| Hardening | On-call basics, restore drill, quarterly DPDP audit, Meta scope self-audit (monthly transcript sample vs intent taxonomy). |

**Milestones:** M3.1 = 10 paying (Month 4). M3.2 = 25 paying + churn <5% + GM >60% (Month 6).

**Exit gate G3 / decision point (end Month 6):**
- **Scale:** all M3.2 targets hit → raise ops capacity, open salon vertical pack, consider seed raise or fund from Xolver services.
- **Pivot:** churn >10% or conversion <40% → diagnosis sprint (2 weeks): is it product quality (containment data) or value (owners use it but won't pay)? Quality → fix. Value → move up-market (multi-doctor clinics ₹9,999+) or switch vertical.
- **Kill:** <10 paying customers AND no vertical shows conversion >40% → stop; harvest the agent core as an Xolver services asset.

---

## Cross-Phase Standards (apply every week)

1. **Eval-gated deploys:** no prompt/model/taxonomy change ships without eval suite pass.
2. **Transcript review ritual:** sample 20 conversations/day (100% for any clinic in its first week) until 25 tenants; feed misses into eval set.
3. **Compliance self-audit:** monthly — random 50 transcripts checked against intent scope; template usage audit; consent-state audit. Logged in compliance register.
4. **Cost report:** weekly per-tenant COGS review; any tenant with GM <40% triggers plan-fit conversation or fair-use enforcement.
5. **Build in public:** one artifact/week from real pilot data (anonymized) → @subhamjena.ai. GTM runs from Week 3, not after launch.
6. **Quality flywheel ritual (TRD §10):** weekly 30-min eval-candidate labeling (eval set +≥50 utterances/wk during pilot); shadow replay required on every prompt/taxonomy PR; nightly LLM-judge trend reviewed in the weekly ritual.

## Effort & Budget Summary

| Phase | Duration | Cash outlay (excl. founder time) |
|-------|----------|----------------------------------|
| 0 | 2 wks | ~₹15K (travel, legal review, misc) |
| 1 | 4 wks | ~₹20K/mo infra+LLM+BSP; pilots free |
| 2 | 6 wks | +₹25K (telephony, STT/TTS testing, native-speaker testers) |
| 3 | 3 mo | ~₹40–60K/mo all-in until revenue covers |

Total cash to Month 6 decision point: ≈ ₹2.5–3.5L. Break-even at ~15–20 Starter customers.
