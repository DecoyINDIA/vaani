# 03 — STRATEGIC OPTIMIZATION

## 1. The recommendation in one paragraph

**Stop hardening, start piloting.** Freeze voice, billing and further acceptance suites. Spend the next four weeks making the WhatsApp journey correct for a real patient (Wave 1), provable on a real model (Wave 2), and operable by a real receptionist (Wave 3), then put it on one real clinic number. No rebuild: the core architecture is sound and should be kept. Buy voice later instead of finishing the custom stack.

## 2. First-principles questions

**Is the right problem being solved?** Probably. Missed calls and slow WhatsApp replies at small clinics are real and the price point is plausible. But the repo contains no evidence of the five LOIs its own plan made a precondition for writing code. The riskiest assumption is no longer technical; it is whether owners will pay and whether patients will complete a booking with a bot. Only a live pilot answers that.

**Is the architecture appropriate?** Yes for the core, over-built at the edges. One FastAPI app, one worker, Mongo, Redis is the right size for 0–50 tenants. The parts built ahead of need: resumable migration tooling for a database with no production data, an erasure ledger with restore replay, a 1,100-line CI with kill-tests, GST invoice rendering. None is wrong; all were premature relative to "a patient sees `[source_ref: faq_fees]`".

**Could something simpler outperform it?** For the conversational layer, yes. Two LLM calls plus a keyword date parser plus per-intent worker branches can become **one structured extraction call** returning intent and slots (date, time, practitioner, service), feeding the existing deterministic flow. Fewer moving parts, better multi-turn handling, lower latency. This is an incremental swap inside `intent.py`/`tool_router.py`, not a rewrite.

**Where is effort being wasted?** (a) Self-certifying on mocks. (b) Custom voice. (c) Docs that restate docs — `docs/knowledge/*`, the 590-line ledger, eight planning files. Cap documentation at one context file and one decision log.

**What would prevent commercial success?** In order: no distribution proof; a dashboard staff will not use; vernacular quality that is asserted, not measured; Meta pricing/policy drift; founder bandwidth spread across WhatsApp + voice + billing + compliance at once.

**What could differentiate it?** Not "AI receptionist" — that is crowded. Candidates, in order of defensibility:
1. **Measured honesty**: a published per-clinic number — bookings completed without staff, with zero wrong facts — backed by the grounding gate that already exists.
2. **Tap-first vernacular booking** that needs no typing, tuned on real Odia/Hinglish traffic (Odia is under-served by the larger vendors).
3. **Operator-grade reliability** (no lost messages, no double bookings) — invisible in a demo, decisive in month three.

## 3. Strategic options compared

| Option | Feasibility | Commercial potential | Dev cost | Risk | Verdict |
|---|---|---|---|---|---|
| **A. WhatsApp-only pilot on current code after a correctness wave** | High — code exists | Validates the business in weeks | ~4 agent-weeks | Low | **Recommended** |
| B. Finish everything (voice + billing + payments) before any pilot | Medium | Delays learning by months | High | High — builds on unvalidated demand | Reject |
| C. Rebuild as an agentic tool-calling assistant | Medium | No gain; weakens the compliance story | High | High | Reject |
| D. Re-platform onto a BSP's flow-builder + thin custom layer | High | Faster onboarding, but surrenders the differentiators and margin | Low | Medium | Keep as fallback if Meta onboarding stalls |
| E. Sell the agent core as an Xolver services asset | High | Bounded | Low | Low | The repo's own "kill" path; keep in reserve |

**On voice specifically:** park the custom Exotel/Sarvam pipeline behind a feature flag (do not delete). When a paying clinic asks for voice, run a two-week bake-off between the in-house pipeline and a managed Indic voice-agent platform that calls Vaani's existing booking tools over HTTP. Decide on measured ₹/min and containment. At a ₹4/min selling price and ~₹3–3.5/min vendor price, gross margin on voice is thin either way; voice should be priced as an add-on that at least breaks even, not as the Pro plan's anchor.

## 4. Product principles for the next quarter

1. **Every patient-visible string is correct, localized, and tenant-specific** before any new feature.
2. **Tap, don't type**: lists and buttons for every decision; free text only to start.
3. **Destructive actions need a confirmation tap** (cancel, reschedule).
4. **The dashboard answers three questions in five seconds**: who is waiting for a human, who is coming today, did anything fail.
5. **One number the owner trusts**: bookings handled end to end, never an invented rupee figure.
6. **Remove before adding**: delete waitlist stubs, the fabricated revenue line, unused templates.

## 5. Prioritization rationale

Ranking uses (patient harm × likelihood) first, then (pilot-blocking), then (learning value ÷ cost).

- **Wave 1 — Correctness (P0):** B-01..B-05, C-02, C-05, D-01, D-05. Small, mechanical, independently testable on mocks. Nothing here needs a business decision.
- **Wave 2 — Real-world proof (P1):** real-model eval harness and thresholds, structured extraction, LLM client hardening, observability, localization, non-text handling, worker concurrency. This is where "works" gets its first honest measurement.
- **Wave 3 — Operable product (P1):** dashboard "Today" view with names and times, re-login, staff notifications to patients, multi-practitioner/service, conversation lifecycle.
- **Pilot gate:** staging on real providers, one clinic, 14 days.
- **Wave 4 — Commercial (P2):** pricing fix, onboarding wizard, credential storage, truthful weekly summary, Razorpay sandbox, then voice decision.

## 6. Decisions that need the owner (cannot be delegated to agents)

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| D1 | Proceed to a WhatsApp-only pilot and freeze voice/billing work | Yes | everything |
| D2 | Starter booking cap (50 + ₹49) vs memo's 350 bookings | Remove the per-booking overage at pilot; meter it silently and revisit at 10 customers | pricing page, `plans.py` |
| D3 | Production models (classifier/extractor, responder, embedding) | Pick after the Wave-2 eval; start with one small fast model for extraction and one mid-tier for responses | Wave 2 |
| D4 | Staff see patient name and phone in the dashboard | Yes — they are the clinic's own patients; keep PII out of ops alerts only | T-009 |
| D5 | Login link delivery channel | WhatsApp authentication template to the staff member's number | T-020 |
| D6 | Verify current Meta India rate card and free-tier rules | Do this week; it can change the margin model | 10 §5 |
| D7 | Slot model vs token/queue model | Ask the first 5 clinics before building more scheduling | Wave 3 |
