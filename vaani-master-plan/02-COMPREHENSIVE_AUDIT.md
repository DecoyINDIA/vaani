# 02 — COMPREHENSIVE AUDIT

Reviewed commit `847d5f5`. Every finding cites code I read. Line numbers are from that commit. Nothing was executed, so each finding is a **code-reading result**, not a reproduced failure; each has a verification step in its task packet.

**Relationship to the repo's own review.** `docs/production-review.md` (6 Nov) listed 20 findings R01–R20; `docs/production-remediation-plan.md` marks all "Complete (code & CI)". I spot-checked the fixes for R01, R03, R04, R05, R08, R09, R12, R14, R17 in current code and they are present. The findings below are **new** — none appears in R01–R20 — and most sit one layer up, in what a patient or receptionist actually sees.

Severity: **P0** patient-visible defect or integrity risk · **P1** blocks a credible pilot · **P2** strategic · **P3** minor.

---

## A. The headline finding: verification is all on mocks

| ID | Finding | Evidence |
|---|---|---|
| **A-01 (P0, process)** | All 191 tests and the 25-case eval run with `USE_MOCK_ADAPTERS=true`: mongomock, a keyword-matching fake LLM, fake WhatsApp sends, zero-vector embeddings. "Macro F1 1.0, 0 hallucinations" measures the mock against itself. No real model, Meta number, Atlas index, Exotel call or Razorpay sandbox has ever been exercised. | `tests/conftest.py:8`; `app/agent/llm.py:13-119` (mock answers "Sharma Dental Clinic … Rs 500" by keyword); `app/kb/embedding.py:15`; `app/channels/whatsapp.py:172-176`; remediation plan prerequisite register: 17/17 "Pending" |
| A-02 (P1, process) | Documentation outweighs product. 80 commits in 3 days alternate code and "record evidence" docs; the remediation ledger is 590 lines; 12 "work packages" were closed in one day. The risk is treating a green CI badge as readiness. The next unit of progress is a live conversation, not another acceptance suite. | `git log`; `docs/production-remediation-plan.md` |

---

## B. Patient-facing defects (verified in code)

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| **B-01** | P0 | **Internal citation tags are sent to patients.** The responder is told to append `[source_ref: …]`; the output gate checks them; nothing removes them before `send_freeform`. A patient would read "The fee is Rs 500. [source_ref: faq_fees]". Voice would speak it. | `responder.py:108`; `inbound.py:516,656-662` (response sent as-is); grep: no `source_ref` handling outside `agent/nodes`, `kb/`, `llm.py`; `voice/session.py:246` |
| **B-02** | P0 | **Every tenant is "Sharma Dental Clinic".** The responder system prompt and classifier prompt hardcode a clinic name and "dental"; static templates say "dental clinic"/"dentist"; the output gate's location regex contains `bhubaneswar`. A second tenant, or any non-dental clinic, gets the wrong identity. | `responder.py:103`; `intent.py:45,55,67`; `templates/__init__.py:17-26,34-38`; `output_gate.py:48` |
| **B-03** | P0 | **Past slots are bookable.** `slots_get` returns every open slot from local midnight; at 3 pm it still offers 9 am. `hold_slot` has no time guard either. | `slots_get.py:33-47`; `engine.py:276-283` |
| **B-04** | P0 | **Cancel executes without confirmation.** If the classifier returns `cancel`, the worker cancels the first active booking it finds for that number — no "are you sure", no choice when there are several. One misclassification destroys an appointment. | `inbound.py:535-552` |
| **B-05** | P0 | **Booking status shows raw UTC.** Reply is `f"Your appointment is {status} for {start.isoformat()}"` on a naive-UTC datetime — e.g. "confirmed for 2026-11-12T04:30:00" for a 10:00 IST slot. | `inbound.py:527-532` |
| **B-06** | P1 | **The booking flow is English-only.** Language is detected per message and discarded. All deterministic copy — picker prompt, "Confirm"/"Choose again", confirmation, slot-taken, cancel, status, opt-out — is hardcoded English. The product's core claim is vernacular. | `inbound.py:224,241,272,311,342,363,393,470,491,532-552,571,608`; `whatsapp.py:356-357,393,397` |
| **B-07** | P1 | **Non-text messages are silently dropped.** Voice notes, images, locations, stickers get no reply ("Skipping non-text"). Voice notes are a primary mode for the target users. | `inbound.py:405-408` |
| **B-08** | P1 | **No multi-turn understanding.** The classifier sees one message with no history. "Kal" in reply to "which day?", or "1" in reply to the numbered capability menu the bot itself sends, is classified cold → out-of-scope loop. | `intent.py:78`; `templates/__init__.py:23` (numbered menu, no handler) |
| **B-09** | P1 | **Date parsing matches substrings.** `"mon" in phrase` fires on "month"/"money", `"sat"` on "satisfied", `"sun"` on "sunna", `"kal"` on "aajkal". No month names ("15 November", "15 tarikh"). Unparseable → silently "today". | `relative_date.py` weekday map + `any(k in phrase …)`; final `return today` |
| **B-10** | P1 | **Time of day is ignored.** "Kal shaam 5 baje" shows the first 10 slots of the day. `parse_colloquial_time` is never called — and has a bug: `baje` is listed as a PM indicator, so "subah 10 baje" → 22:00. | `tool_router.py:67-78`; `inbound.py:575`; `relative_date.py` `pm_indicators` |
| **B-11** | P1 | **One doctor, one service.** `Practitioners.find_one({})` takes whichever practitioner comes first; service is always `"Consultation"`. Starter is sold for 3 practitioners. | `tool_router.py:71`; `inbound.py:587` |
| **B-12** | P2 | **No "no slots that day" recovery.** Empty day falls to the LLM with "No slots available"; no next-available suggestion. | `inbound.py:554-561`; `responder.py:82` |
| **B-13** | P2 | WhatsApp conversations never close (only voice sets `closed`). One eternal thread per contact: `wa_conversations` usage meters once ever; the "previous abuse/complaint" check never resets; history grows unbounded. | `inbound.py:103-118,419-425`; `scope_gate.py:64-70`; grep `"closed"` |
| **B-14** | P2 | Patients are not told when staff cancel or move their booking from the dashboard. | `routes.py:274-302` |

---

## C. Owner/staff surface

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| **C-01** | P1 | **The dashboard cannot run a front desk.** Inbox rows read "Conversation a1b2c3", time is the literal string `now`; appointments show "Patient reference …8chars", no date, time or doctor. Staff cannot see who is coming when. | `App.tsx` Inbox (`<time>now</time>`), Bookings table; `routes.py:40-54,215-229` return raw docs without joins |
| C-02 | P1 | **Staff reply outside the 24h window returns HTTP 500.** `send_freeform` raises `WindowClosedError`; the route does not catch it (nor `AmbiguousDeliveryError`, `SuppressedRecipientError`). | `routes.py:151-156` |
| C-03 | P1 | **No way to log in twice.** A magic token is minted only by an owner calling `/auth/invitations`, returned in the API response (not delivered), and consumable only while `status == "invited"`. After the refresh token lapses or on a new device there is no "send me a link". The first owner must be created out of band. | `sessions.py:102-171` |
| C-04 | P1 | `last_msg_at` is never updated on WhatsApp inbound, so the inbox sort is effectively by `_id`. | grep `last_msg_at`: only `escalate.py`, voice |
| C-05 | P1 | `GET /api/settings` returns the whole tenant document to any staff member, including the WhatsApp credential env-var name and billing fields. | `routes.py:440-445` |
| C-06 | P2 | No slots/contacts endpoints → staff cannot make a walk-in or phone booking although `POST /bookings` exists. No schedule, holiday, practitioner or staff-invite UI. No KB delete. | `routes.py` route list |
| C-07 | P2 | KB entries created in the dashboard have no `key`, so their citation id is a Mongo ObjectId and the structured fallback (lookup by `faq_*` key) can never find them. | `routes.py:422-436`; `retrieval.py:20,29` |
| C-08 | P2 | **The weekly ROI message fabricates revenue**: `recovered_count * 1000` rupees, "recovered" = any booking outside a hardcoded 09–18 window, sent Sunday 23:00. This contradicts the brand promise of never making up an answer. | `weekly_summary.py:27,65-67,80` |
| C-09 | P3 | Dashboard is one 132-line file with ~1,000-character lines, no tests, `lint` = `tsc`. Tokens in `sessionStorage`. | `dashboard/src/App.tsx`, `package.json` |

---

## D. Architecture, performance, operations

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| **D-01** | P1 | **Cannot start a WhatsApp-only pilot.** `validate_runtime` demands Exotel, Sarvam, Razorpay keys and a GSTIN in staging/prod regardless of what is enabled. | `config.py:92-124` |
| **D-02** | P1 | **Throughput ceiling of one message at a time, platform-wide.** The worker awaits each event serially; each needs 2 LLM calls (30 s timeout each). One slow call stalls every tenant. `CONSUMER = "worker-1"` is a constant, so a second worker process shares the consumer identity. The graph is recompiled per message. | `inbound.py:37,508,908-910`; `llm.py:158` |
| D-03 | P1 | **No observability.** `sentry_dsn` is read and never used; no structured logs, no request ids, no LLM latency/token/cost capture — so COGS and the p50 ≤ 3 s goal are unmeasurable. | grep `sentry`; `llm.py` |
| D-04 | P1 | **LLM client is fragile.** New `httpx` client per call; fallback only on non-200 (not on timeout); no JSON mode — the classifier parses free text and treats any parse failure as an outage → handoff. | `llm.py:156-173`; `intent.py:84-106` |
| D-05 | P1 | `ops/` is not in the image (`COPY app ./app` only), so onboarding, erasure and rotation CLIs cannot run where the secrets are. | `Dockerfile:33` |
| D-06 | P2 | Tenant WhatsApp tokens live in process env keyed by a name in the tenant doc → restart per onboarding; no path to Meta Embedded Signup. | `whatsapp.py:100-116` |
| D-07 | P2 | Scheduler rides inside the consumer loop on a 15-minute sleep; a failed/crashed `slot_expansion` job row blocks retry until the next local day. Holiday edits do not close already-generated open slots. | `inbound.py:803-854`; `engine.py:152-166,76-81` |
| D-08 | P2 | Prompt-injection surface: patient text and WhatsApp profile name are interpolated into prompts unescaped; the profile name lands in the **system** prompt. The numeric gate limits damage to fees/times; names and services are unguarded. | `responder.py:137,145` |
| D-09 | P3 | Config drift: `.env.example` has `JWT_SECRET=changeme` and `INVOICE_SAC_CODE=998314` vs code default `998313`; audit TTL is hardcoded 90 d, ignoring `audit_log_retention_days`. | `.env.example:6,56`; `config.py:69`; `collections.py:466` |
| D-10 | P3 | Dead/test code in production paths: `claim_waitlist_slot`, `parse_colloquial_time`, `location_landmark` template, `b"TALK"` test signal in barge-in. | `engine.py:526`; `barge_in.py:22` |

**What to keep unchanged:** `TenantScoped` accessors + CI grep; hold→confirm booking engine; Mongo-as-queue-of-record with leases; outbound-intent ledger; scope-gate topology; purpose-typed auth; erasure ledger. These are the asset.

---

## E. Security summary

No new critical vulnerability found. Webhooks are HMAC-verified; owner routes derive tenant from the token; magic tokens are hashed and single-use; Redis is no longer published. Residual items: C-05 (over-broad settings read), D-08 (injection), magic-consume rate limit keyed on `request.client.host` (one bucket behind a proxy), no refresh-token reuse detection, alerts webhook is unauthenticated. All P1–P3.

---

## F. Product and business findings

| ID | Sev | Finding | Basis |
|---|---|---|---|
| **F-01** | P1 | **Pricing is internally inconsistent.** Starter includes 50 bookings then ₹49 each; the pricing memo's "standard tenant" makes 350 bookings/month → ₹17,699 before GST, above both the ₹2,999 headline and the ₹15K UPI-Autopay no-AFA limit the plan relies on. | `plans.py`; `ops/pricing_memo.md §3`; `04-gtm-pricing.md §2` |
| **F-02** | P1 | **Margin model rests on a Meta rule that may have changed.** The memo assumes in-window service replies are free without limit. Vendor notices (AiSensy, WATI — unverified against Meta's rate card) say that from 1 Oct 2026 service messages are free only up to 1,000 per number per month and in-window utility templates are billable. At 1,000 conversations × ~4 bot messages this matters. **Must be verified.** | external, see 10 §5 |
| F-03 | P1 | **Voice is the most expensive, least proven part and is now buyable.** ~1,300 lines of custom Exotel/Sarvam plumbing, never run live, versus managed Indic voice agents advertised from ~₹3/min including telephony, against a planned ₹4/min overage price. | `app/gateway/exotel.py`, `app/channels/voice/*`; external |
| F-04 | P1 | Fixed-slot booking may not match clinics that run token/walk-in queues. Untested assumption; interview before building more scheduling. | hypothesis |
| F-05 | P2 | Onboarding is a JSON file plus a CLI plus an env var plus a restart — far from the "live in 24 hours" pitch. | `ops/onboard_tenant.py` |
| F-06 | P2 | The market already has several low-priced entrants; "AI receptionist on WhatsApp" is not differentiating by itself. | external |

---

## G. AI assessment

The architecture choice — closed intents, code-enforced scope, LLM only for grounded phrasing — is right for a regulated, low-ticket product and should stay. The gaps are execution: no real-model evaluation (A-01), no context to the classifier (B-08), no structured output (D-04), no cost telemetry (D-03). AI that would add value next: a single structured extraction call returning `{intent, date, time, practitioner, service}` (replaces the brittle keyword date parser), and transcription of WhatsApp voice notes. AI that should **not** be added now: agentic tool-calling, long-term patient memory, no-show prediction, a fine-tuned classifier.
