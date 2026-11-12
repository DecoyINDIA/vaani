# 05 — MASTER ROADMAP

Evidence for each initiative is the audit finding in column **Audit** (see `02-COMPREHENSIVE_AUDIT.md` for file and line). Complexity: S ≤ half a day of agent work, M ≈ 1–2 days, L ≈ 3–5 days. Confidence is my confidence that the problem is real **and** the fix is as described.

## Milestones

| Milestone | Exit condition | Target |
|---|---|---|
| **M1 Correct** | Wave 1 merged; golden transcript shows no tag, right clinic name, local times, cancel needs a tap | week 1 |
| **M2 Proven** | Real-model eval ≥ thresholds in `09`; p50 reply ≤ 4 s measured; Hindi/Hinglish/Odia flow copy reviewed by a native speaker | week 3 |
| **M3 Operable** | A receptionist can find today's patients by name and time, reply, and log back in unaided | week 4 |
| **M4 Pilot live** | One clinic, real number, 14 days, zero wrong-fact incidents, ≥ 20 bot-completed bookings | week 6–7 |
| **M5 Paid** | First UPI-Autopay charge collected; pricing decision D2 made | week 10 |

## Wave 1 — Correctness (P0) · immediately actionable, no business input

| ID | Audit | Solution | Benefit | Cx | Deps | Risk | Conf | Verification | Success criterion |
|---|---|---|---|---|---|---|---|---|---|
| W1-01 | B-01 | `app/agent/render.py::strip_citations`, applied before every patient send (WhatsApp + voice) | Patients never see internal tags | S | — | Low | High | unit + inbound test | No `[source_ref` in any outbound text or stored outbound message |
| W1-02 | B-02 | Tenant name / business type injected into prompts; generic templates; CI grep | Multi-tenant correctness | M | — | Med (mock LLM coupling) | High | tests + grep | Zero `Sharma`/`dental`/`Bhubaneswar` literals in `app/agent` outside `llm.py` |
| W1-03 | B-03 | Lead-time filter in `slots_get`; `start > now` guard in `hold_slot` | No bookings in the past | S | — | Low | High | unit tests with frozen time | Past/too-soon slot never offered nor holdable |
| W1-04 | B-04 | Two-step cancel with `cancel:confirm` / `cancel:keep` buttons | No accidental cancellations | M | W1-05 | Med | High | flow test | `cancel` intent alone never changes a booking |
| W1-05 | B-05 | `app/booking/timefmt.py`; used for status reply | Human-readable local time | S | W1-01 | Low | High | unit test (IST) | No `isoformat()` reaches a patient |
| W1-06 | C-02 | Map send exceptions to 409 with `code` | Staff see a reason, not a 500 | S | — | Low | High | route tests | 3 error codes covered |
| W1-07 | C-05 | Allow-listed settings response | No credential-reference leak | S | W1-06 | Low | High | route test | Response keys ⊆ allow-list |
| W1-08 | D-01, D-09 | `ENABLE_VOICE/PAYMENTS/BILLING` flags; conditional validation + routers; `.env.example` fixes | WhatsApp-only pilot can boot | M | — | Med (security tests) | High | config tests | Staging boots with only WhatsApp + LLM secrets |
| W1-09 | D-05 | `COPY ops ./ops` in image; CI smoke runs `python -m ops.onboard_tenant --help` | Ops CLIs usable in prod | S | — | Low | High | image smoke | Command exits 0 in the built image |
| W1-10 | B-07 | Polite reply to audio/image/location/etc.; ignore reactions | Nobody is ignored | S | W1-04 | Low | High | inbound tests | Each unsupported type gets exactly one reply |
| W1-11 | C-01, C-04 | View models with contact name/phone, slot start, practitioner; maintain `last_msg_at` | Data the desk needs | M | W1-07 | Med | High | route tests | Fields present, tenant-scoped |
| W1-12 | C-01 | Dashboard shows names, real timestamps, appointment date/time | Usable inbox and list | M | W1-11 | Low | High | `npm run build`, manual | No literal `now`; date/time column present |
| W1-13 | B-09, B-10 | Word-boundary matching, month names, fix `baje` AM/PM bug | Right day offered | S | — | Low | High | table-driven tests | 30-case table passes |

## Wave 2 — Real-world proof (P1)

| ID | Audit | Solution | Cx | Deps | Risk | Conf | Success criterion |
|---|---|---|---|---|---|---|---|
| W2-01 | B-06 | `app/i18n/` string table ×4 languages; persist `conversation.lang`; localized date labels | M | Wave 1 | Med (translation quality) | High | No English literal in flow code; native review signed |
| W2-02 | A-01 | Real-model eval: ≥300 labelled utterances, nightly credentialed workflow, thresholds | L | D3 | Med | High | Report artifact with per-language F1 and grounding violations |
| W2-03 | B-08, B-10 | Single JSON `understand` call with last-3-turn context returning intent + date/time/hints | L | W2-02, W2-04 | High | Med | Booking path uses 1 LLM call; date accuracy ≥ 95% on eval |
| W2-04 | D-04 | Shared client, 8 s timeout, retry/fallback, JSON mode, `llm_calls` telemetry | M | — | Low | High | p95 latency and cost per conversation queryable |
| W2-05 | D-03 | Sentry + JSON logs with tenant/conversation ids | S | — | Low | High | An injected exception appears in Sentry with ids, no PII |
| W2-06 | D-02 | Concurrent worker with per-contact lock; unique consumer id; graph compiled once | L | — | High | Med | 20 parallel conversations, order preserved, no duplicate sends |
| W2-07 | D-07 | Scheduler as its own entrypoint; retry failed job rows | M | W2-06 | Med | High | Killing the worker does not stop reminders |
| W2-08 | — | Golden multi-turn transcript tests per language | M | W2-01 | Low | High | 8 journeys × 4 languages in CI |
| W2-09 | B-08 | Interactive capability menu (`menu:*`) replaces numbered text | S | W2-01 | Low | High | Every menu tap is handled deterministically |

## Wave 3 — Operable product (P1)

| ID | Audit | Solution | Cx | Deps | Needs decision |
|---|---|---|---|---|---|
| W3-01 | C-03 | `POST /auth/magic/request` + WhatsApp auth template + login screen | M | W1-08 | D5; template approval |
| W3-02 | C-01 | `GET /api/today` + "Today" tab as the default view | M | W1-11 | — |
| W3-03 | B-11 | Practitioner and service pickers when > 1 | M | W2-01 | — |
| W3-04 | B-13 | Close after 24 h idle; new conversation per session; fix metering key | M | W2-07 | — |
| W3-05 | B-14 | Template to patient on staff cancel/reschedule | S | — | template approval |
| W3-06 | C-06 | `/api/slots`, `/api/contacts`, manual booking form | M | W1-11 | D7 |
| W3-07 | C-07 | KB `key` slug + delete endpoint | S | — | — |
| W3-08 | B-12 | Next-available-day suggestion | S | W2-03 | — |
| W3-09 | C-09 | Split `App.tsx`, add vitest + one Playwright smoke | M | W1-12 | — |
| W3-10 | D-08 | Delimit untrusted text; remove profile name from system prompt | S | W2-03 | — |

## Pilot gate — human/operator tasks (not delegable to coding agents)

| ID | Task | Owner |
|---|---|---|
| H-01 | Verify Meta rate card + free-tier rules; confirm WABA status; choose direct Cloud API vs BSP | Founder |
| H-02 | Provision staging: Atlas (replica set + Search indexes), VPS, domain, TLS | Operator |
| H-03 | Create OpenRouter key; choose models after W2-02 | Founder |
| H-04 | Submit/confirm 5 utility templates + 1 authentication template in 4 languages | Founder |
| H-05 | Sign one pilot clinic; load its KB, schedule, holidays; native-speaker copy review | Founder |
| H-06 | Run the live staging smoke (script in `09`), then 14-day pilot with daily transcript review | Founder |

## Wave 4 — Commercial and strategic (P2/P3) · mostly gated on decisions

| ID | Audit | Initiative | Gate |
|---|---|---|---|
| W4-01 | F-01 | Implement the chosen Starter packaging in `plans.py` and copy | D2 |
| W4-02 | C-08 | Truthful weekly summary (no invented rupees; Monday 09:00 local; tenant hours) | template re-approval |
| W4-03 | D-06 | Encrypted per-tenant WhatsApp credential; no restart on onboarding | — |
| W4-04 | F-05 | Operator onboarding form → validated config → apply | W4-03 |
| W4-05 | D-10 | Remove waitlist stubs, unused template, test signal | — |
| W4-06 | F-03 | **Discovery:** 2-week voice bake-off, in-house vs managed platform | a paying clinic asks for voice |
| W4-07 | B-07 | **Discovery:** WhatsApp voice-note transcription cost/accuracy | pilot data shows ≥ 10% audio messages |
| W4-08 | — | Razorpay sandbox end-to-end for subscriptions | M4 reached |

## Release strategy

Trunk-based; one task = one PR; CI must be green; deploy the CI-built digest to staging; promote the same digest to the pilot host. Wave 1 ships as three PR chains (see `08`). No release contains both a prompt change and a flow change without the golden transcripts passing.

## What is deliberately not on the roadmap

Custom voice completion, WhatsApp Flows forms, no-show prediction, patient memory/rebook, CSAT, referral loops, multi-city language packs, EMR integrations. Each is plausible later; none moves M4.
