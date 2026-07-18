# TDD Loop Plan — Project Vaani

**Version:** 1.0 | **Date:** 18 Jul 2026 | **Owner:** Subham Jena (Xolver)
**Scope:** the execution discipline layered on top of [06-engineering-plan.md]. Same tasks, same milestones, same gates — reorganized into strict **test-driven loops**: write the tests first (red), build until they pass (green), refactor, close the loop, only then start the next. This doc is the answer to "how do we know each piece works before stacking the next one on top."

---

## 0. The Rules (non-negotiable)

1. **Red first.** A loop opens by writing its tests — failing. For deterministic code that means pytest. For agent behavior (intent, grounding, tone) the **eval suite IS the test suite**: the eval set + threshold is written before the node it judges. An eval threshold (F1 ≥85%, hallucination = 0) is an assertion like any other.
2. **A loop closes only when its full green bar passes** — its own tests AND every previous loop's tests (cumulative regression). Tests are never deleted or weakened to close a loop; if a test was wrong, fixing it is a reviewed change with a note.
3. **No loop N+1 while loop N is red.** No parallel half-open loops. If a later loop breaks an earlier loop's tests, the later loop stops until the regression is fixed.
4. **CI is the referee.** Every green bar is a CI job, not a human's memory. "Works on my machine / worked yesterday" doesn't close loops — the pipeline run does. Human-executed checks (UAT, chaos drill, restore drill, scripted calls) get a filed checklist artifact in `ops/` — a checklist run is a test run.
5. **The pilot is a loop too.** Real transcripts are test inputs we didn't write; every miss becomes an eval case (quality flywheel, TRD §10) — production failures convert into permanent regression tests within 48h.
6. **Loop ≠ week.** Loops map onto the Week 3–6 plan but close on green, not on Friday. If a loop finishes early, the next starts early; if it's red, the schedule slips *inside* the phase and scope gets cut per Build Plan rules — the green bar never gets lowered.

**Loop template:**

> **Ln — Name** *(feeds milestone; eng-plan tasks)*
> **Red:** tests written first.
> **Green:** build until this bar passes.
> **Done means:** the one-line demo/proof.

---

## Phase 1 — WhatsApp MVP as 14 loops

### L0 — Harness *(M1.1; tasks 3.1)*
**Red:** CI pipeline exists and runs an intentionally failing placeholder test; `GET /health` test (404s — no app yet); eval harness invocable with an empty set (exits non-zero on "no dataset").
**Green:** `docker compose up` serves `/health` 200; CI green on lint + mypy + pytest + eval-harness smoke; dev/prod env split loads from `config.py`.
**Done means:** a one-line change pushed → CI verdict in <5 min. The referee exists before any player.

### L1 — Webhook gateway *(M1.1; task 3.2)*
**Red:** invalid `X-Hub-Signature-256` → 403; valid → 200 in <5s with processing deferred; same `message_id` delivered twice → exactly one enqueued (Redis SETNX idempotency); unknown `wa_number` → acked and dropped with audit entry; malformed payload → acked, quarantined, never crashes the worker.
**Green:** all pass against a mocked Meta payload corpus (real payload samples committed as fixtures).
**Done means:** Meta can double-deliver, garbage-deliver, or probe us — nothing duplicates, nothing crashes, everything acks fast.

### L2 — Queue durability *(M1.1 + TRD §9; tasks 3.3, part of 5.10)*
**Red:** kill worker mid-message → message reprocessed, not lost; poison message → dead-letter after 3 retries with audit entry; **Redis down → webhook still 200-acks and messages land in the Mongo fallback queue; workers drain it on recovery — zero dropped** (degradation ladder row, tested now, not in Week 5).
**Green:** chaos-style integration tests pass in CI (containerized Redis stopped/started by the test).
**Done means:** "a message is never dropped" is a passing test, not a slogan.

### L3 — Data layer & tenant isolation *(M1.1; task 3.4)*
**Red:** every collection accessor rejects calls without explicit `tenant_id` (lint rule test: raw `db[...]` outside `models/` fails CI); cross-tenant read/write probes on every accessor → denied; unique index on `(tenant_id, practitioner_id, start)` enforced (duplicate insert test); `seed_tenant.py` creates a demo clinic in <1 min (timed test).
**Green:** isolation probe suite 100% denied; seed idempotent (run twice → one tenant).
**Done means:** cross-tenant leakage is impossible by construction — proven by probes, not review.

### L4 — Language & intent (first eval loop) *(M1.1 gate; tasks 3.5, 3.6)*
**Red:** **the 150-utterance seed eval set is written before the classifier** (40/lang from interview transcripts + synthetic; this is the failing test); lang-detect unit tests: Devanagari→hi, Odia script→or, Latin-script Hindi→hi-Latn, English→en, mixed-script edge cases; scope-gate test: below-threshold confidence twice → handoff path.
**Green:** intent F1 ≥85% per language on the seed set; CI eval gate wired (any prompt change re-runs it).
**Done means:** **M1.1** — echo-with-intent bot live on test number; the bot's brain has a report card before it has a mouth.

### L5 — Booking engine *(M1.2; tasks 4.1–4.3)*
**Red:** 500-concurrent race test → 0 double-bookings (the test exists and fails against a naive implementation first); hold expires at 120s → slot reopens; holiday calendar: no slots generated on Raja/Rath Yatra/custom closure (fixture calendar); relative-date resolver table tests: "kal"→tomorrow, "parso"→+2d, "agle somvar"→next Monday, Indic numerals, "shaam ko 4 baje"→16:00; **booking tool rejects any call without `date_confirmed=true`**; 20 relative-date eval utterances → 100% confirmed-before-booked.
**Green:** race test green in CI (nightly job); all resolver tables pass.
**Done means:** the only component that can cost a clinic money (double-booking, wrong day) is the most-tested component in the repo.

### L6 — Interactive booking UX *(M1.2; task 4.7 + TRD §9 menu mode)*
**Red:** scripted conversation test: intent→list picker→button confirm completes a booking in ≤3 taps (driven at the API level with recorded interactive-message payloads); free-text fallback books without the picker; stale button tap (slot gone) → next-best offered, never a false confirm; **menu-mode test: with the LLM client mocked to raise, a booking still completes end-to-end via picker + deterministic tools**.
**Green:** all conversation scripts pass; per-step conversion counters emit to the daily report.
**Done means:** bookings work when the AI is down — resilience and conversion fell out of the same test.

### L7 — KB & grounded responder *(M1.2 gate; tasks 4.4–4.6)*
**Red (all written before the responder exists):** retrieval eval — 50 seeded Q→entry pairs, top-3 hit ≥90%; **hallucination eval — 30 trap questions where the KB lacks the answer → 0 fabricated facts** (correct behavior: "I'll check with the clinic" + escalate); output-gate tests: uncited fee/time/service/address claim → rejected → one regenerate → fallback template; **graph-topology test: `out_of_scope` and `medical_question` inputs can never reach the LLM responder node** (asserted on the compiled graph, not on prompts); template completeness test: every static template exists in all 4 languages, respectful register (no तू/tum in system copy — grep test).
**Green:** all evals ≥ thresholds; hallucination = 0.
**Done means:** **M1.2** — end-to-end booking in Hindi + Hinglish in ≤3 taps; the anti-hallucination guarantee is a CI gate.

### L8 — Handoff *(M1.3; tasks 5.1–5.2)*
**Red:** each trigger (human_request, 2× low-confidence, medical/complaint, abuse) → `state=human` and bot silenced (post-trigger inbound gets no bot reply — tested); staff alert dispatched ≤30s (clock-controlled test); resolve&return → `state=bot` with context summary injected (post-return reply references the human resolution — eval case); SLA timers written to `escalations`.
**Green:** all triggers covered; one manual device test: alert on a real staff phone <30s, filed in `ops/`.
**Done means:** "a patient is never stranded" has a test per trigger.

### L9 — Owner API & dashboard *(M1.3; tasks 5.3, 5.7)*
**Red:** JWT tests (expired access token → 401, refresh flow, tampered token); **every owner_api route probed cross-tenant → 100% denied** (extends L3's suite to the HTTP layer); route contract tests for TRD §5.2.
**Green:** probe suite green; dashboard UAT checklist executed by 2 non-technical testers unaided — filed in `ops/` (human test run, rule #4).
**Done means:** the owner surface is provably tenant-safe before an owner touches it.

### L10 — Audit, metering, DPDP *(M1.3; tasks 5.4–5.6)*
**Red:** pick a random fixture conversation → reconstruct it end-to-end from `audit_log` alone (test asserts equality with the source transcript); no send path bypasses `audit.py` (import-graph lint test); cost report totals match metered fixtures; **erasure test: `dpdp_delete.py` on a fixture contact → PII gone from every collection, audit retained pseudonymized, booking integrity intact**; consent-notice versioning: first contact gets notice, second doesn't, version bump re-triggers.
**Green:** all pass; daily cost report lands on WhatsApp (manual check filed).
**Done means:** compliance obligations are executable and re-runnable, not documented intentions.

### L11 — CSAT & quality flywheel *(M1.3; task 5.9 + TRD §10)*
**Red:** 👎 tap → `eval_candidates` row ≤1 min (clock test); escalations and output-gate rejections auto-queue; 5% random sampler is actually ~5% (statistical test on fixtures); **shadow-replay harness test: a prompt-change PR without a replay report fails CI** (the CI rule itself is under test); replay of a fixture week diffs decisions correctly.
**Green:** flywheel plumbing green; first real labeling ritual scheduled.
**Done means:** from here on, every production failure is one label away from being a permanent regression test.

### L12 — Degradation ladder chaos loop *(M1.3 gate; task 5.10 + TRD §9)*
**Red:** the chaos drill script in `ops/` is written as an executable checklist with assertions: kill primary LLM → failover; kill both LLMs → menu mode books (re-runs L6's test in staging); kill classifier → keyword pre-router routes top intents; kill Atlas Search → structured fields still answer; kill Redis → re-runs L2 in staging; circuit breakers open after 5 failures, half-open at 30s (unit-tested).
**Green:** full drill executed once in staging, every assertion holds, results filed.
**Done means:** **M1.3** — full P0 UAT passes; eval set at 300 utterances, F1 ≥90%, hallucination = 0; every failure mode has been caused on purpose once.

### L13 — Production & onboarding *(M1.4 gate; tasks 6.1–6.5)*
**Red (proofs, mostly human-executed with filed artifacts):** prod smoke suite (health, webhook echo, send path) runs post-deploy automatically; **restore drill: Atlas restore to staging, timed — RTO ≤15 min asserted**; KB auto-draft test on 3 real clinic websites → draft KB with ≥80% of structured fields filled; onboarding checklist per clinic; transcript-review digest generates from day-1 data.
**Green:** 5 clinics live; clinic #5 onboarded ≤1h via auto-draft; first organic booking with zero human help.
**Done means:** **M1.4.** Pilot begins — and the pilot itself is now the outermost test loop (rule #5), measured against gate G1.

---

## Phase 2 — Voice as 3 loops

### L14 — STT bake-off (a test that picks the vendor) *(M2.1; ADR-05)*
**Red:** the bake-off harness + labeled Phase-0 corpus (50 calls) is the test; pass bar defined before running: WER per language, latency-to-first-partial ≤300ms, ₹/min ≤ budget. The realtime speech-to-speech candidate runs the same bar.
**Green:** one architecture wins on data; ADR-05 finalized with the results table committed.
**Done means:** the vendor decision is a reproducible experiment, not a preference.

### L15 — Call loop & latency *(M2.1–M2.2)*
**Red:** per-hop latency assertions instrumented as tests (STT partial ≤300ms, LLM first token ≤700ms, TTS first audio ≤400ms, end-to-end ≤2.0s happy path); barge-in kills TTS (test with injected caller audio); budget slip auto-injects filler ack; DTMF fallback routes correctly; consent line plays before any processing (blocking assertion, per Q3).
**Green:** synthetic call suite green; latency dashboard live.
**Done means:** the latency budget is enforced by machines before humans dial in.

### L16 — Scripted human calls *(M2.2–M2.3 gates)*
**Red:** 20-call script (native Hindi + Odia speakers, real phones, ambient noise) with per-call pass criteria written first: task success, zero wrong-fact utterances, transfer works.
**Green:** ≥80% task success, wrong facts = 0, filed in `ops/`; then 100 real calls → containment ≥50%, COGS ≤₹4/min → gate G2 or park voice.
**Done means:** voice ships only after humans it was built for say it works.

---

## Phase 3 — Monetization loops (pattern, applied per feature)

Every Phase-3 feature (ROI summary, billing/GST, reminders, payments, backfill, Flows A/B, patient memory, fine-tune) runs the same micro-loop — no exceptions for "small" features:

1. **Red:** correctness tests from fixtures first — e.g. ROI summary: recovered-booking attribution computed from a fixture audit log matches hand-calculated truth (this number goes in front of paying customers and ASCI applies — it gets the L5 treatment); GST invoice: totals, SAC, GSTIN fields validated against CA-approved samples; backfill: cancel event → offer to waitlist ≤60s, first-tap-wins race test (reuses L5's race harness); classifier fine-tune: must beat the incumbent on the full eval suite per language or it doesn't deploy.
2. **Green:** feature tests + full cumulative regression + shadow replay (if it touches prompts/taxonomy).
3. **Close:** cost metered, audit covered, doc line in the runbook — then the next feature opens.

---

## Loop → milestone → gate map

| Loops | Closes | Phase gate it feeds |
|-------|--------|---------------------|
| L0–L4 | M1.1 echo-with-intent, F1 ≥85% | — |
| L5–L7 | M1.2 booking end-to-end, race-safe, hallucination 0 | — |
| L8–L12 | M1.3 full P0 UAT, F1 ≥90% | — |
| L13 | M1.4 five clinics live | **G1** (measured wks 6–8) |
| L14–L16 | M2.1–M2.3 | **G2** |
| Phase-3 micro-loops | M3.1, M3.2 | **G3** |

**Standing rule recap:** green bar never lowers; red blocks the next loop; production failures become tests within 48h; the checklist artifact in `ops/` is the test run for anything a human executes. Build one loop, test it, pass it — then the next.
