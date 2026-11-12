# 06 — AGENT TASKS

Each packet is self-contained when read together with `../07-AGENT_CONTEXT.md`. Baseline commit `847d5f5`. One packet = one branch = one PR.

## Wave 1 — full packets (ready to assign)

| ID | Title | Tier | Chain | File |
|---|---|---|---|---|
| W1-01 | Strip internal citation tags from patient messages | Small | A1 | `W1-01-strip-citation-tags.md` |
| W1-05 | Human-readable local appointment times | Small | A2 | `W1-05-local-time-rendering.md` |
| W1-04 | Two-step cancellation with confirm buttons | Medium | A3 | `W1-04-cancel-confirmation.md` |
| W1-10 | Reply to unsupported message types; maintain `last_msg_at` | Small | A4 | `W1-10-unsupported-media-reply.md` |
| W1-06 | Staff reply: map delivery errors to 409 | Small | B1 | `W1-06-staff-reply-errors.md` |
| W1-07 | Allow-list the settings response | Small | B2 | `W1-07-settings-allow-list.md` |
| W1-11 | Owner API view models (names, times) | Medium | B3 | `W1-11-owner-api-view-models.md` |
| W1-12 | Dashboard shows names, times, timestamps | Medium | B4 | `W1-12-dashboard-names-times.md` |
| W1-02 | Remove hardcoded clinic identity | Medium | C | `W1-02-dehardcode-tenant-identity.md` |
| W1-03 | Never offer or hold past slots | Small | D | `W1-03-past-slot-guard.md` |
| W1-08 | Feature-flagged runtime validation | Medium | E | `W1-08-feature-flag-runtime.md` |
| W1-09 | Ship `ops/` in the image | Small | F | `W1-09-ops-in-image.md` |
| W1-13 | Date parser: word boundaries, months, time bug | Small | G | `W1-13-relative-date-fixes.md` |

Chains A and B are **sequential inside the chain** (shared files: `app/workers/inbound.py` for A; `app/owner_api/routes.py` and `dashboard/src/App.tsx` for B). Chains A–G run in parallel with each other.

## Wave 2 — full packets (assign only after Wave 1 has merged and INT-1 has passed)

These were written against commit `847d5f5` **before** Wave 1 was implemented. They refer to code by symbol name, not line number, and each lists the Wave 1 symbols it expects. Before assigning one, the orchestrator spends five minutes checking its "Repository Context" against the merged code and corrects the packet if anything moved.

| ID | Title | Tier | Order | File |
|---|---|---|---|---|
| W2-04 | LLM client: shared connection, timeout, retry, JSON mode, telemetry | Medium | 1 | `W2-04-llm-client-hardening.md` |
| W2-05 | Structured logs + Sentry (needs dependency approval) | Small | 2a | `W2-05-observability.md` |
| W2-02 | Real-model eval harness, dataset, nightly workflow | Advanced (dataset) / Medium (harness) | 2b (parallel with 2a) | `W2-02-real-model-eval.md` |
| W2-01 | Localized flow strings + conversation language | Medium + native review | 3 | `W2-01-i18n-flow-strings.md` |
| W2-03 | Structured "understand" call; skip responder on booking paths | Advanced + review | 4 | `W2-03-structured-understand.md` |
| W2-08 | Golden transcripts ×4 languages | Medium | 5 | `W2-08-golden-transcripts.md` |
| W2-09 | Tappable capability menu | Medium | 6 | `W2-09-interactive-menu.md` |
| W2-06 | Concurrent worker, per-patient ordering | Advanced + review | 7 | `W2-06-worker-concurrency.md` |
| W2-07 | Scheduler as its own process | Medium | 8 | `W2-07-scheduler-split.md` |

Wave 2 is mostly **sequential** because six of the nine packets edit `app/workers/inbound.py`. Only W2-02 runs in parallel (it touches `app/agent/nodes/intent.py`, `responder.py` and `evals/`).

## Waves 3–4 — PENDING packets

Specified at initiative level in `../05-MASTER_ROADMAP.md` and architecturally in `../04-TARGET_ARCHITECTURE.md`. Full packets are **not yet written**; write each one after its dependencies have merged. Do not assign them from this table.

| ID | Title | Tier | Why not yet packetized |
|---|---|---|---|
| W3-01 | Self-serve login link | Medium | decision D5 + template approval |
| W3-02 | `/api/today` + Today tab | Medium | after W1-11/12 |
| W3-03 | Practitioner and service pickers | Medium | after W2-01 |
| W3-04 | Conversation lifecycle + metering key | Medium | after W2-07 |
| W3-05 | Notify patient on staff cancel/move | Small | template approval |
| W3-06 | Slots/contacts endpoints + manual booking | Medium | decision D7 |
| W3-07 | KB `key` slug + delete | Small | packet pending |
| W3-08 | Next-available-day suggestion | Small | after W2-03 |
| W3-09 | Split `App.tsx`; vitest + Playwright smoke | Medium | after W1-12 |
| W3-10 | Prompt-injection hardening | Small | after W2-03 |
| W4-01…08 | Commercial wave | mixed | gated on decisions D2, D6 and pilot data |

## Bounded discovery tasks (assign to a medium agent, read-only, 1 hour cap each)

| ID | Question | Output |
|---|---|---|
| DISC-01 | Are `settings.bsp_access_token`, `bsp_waba_id`, `bsp_phone_number_id` read anywhere other than `app/config.py`? | grep result + recommendation (feeds W1-08) |
| DISC-02 | Does `run_monthly_invoices` do anything harmful when no tenant has a subscription and `xolver_gstin` is empty? | code trace of `app/workers/billing.py` and `app/billing/invoice.py` |
| DISC-03 | Which existing tests create slots with a start time in the past relative to "now"? | list of test names (feeds W1-03) |
| DISC-04 | Does `app/channels/voice/session.py` post-process the graph `response` before TTS? | lines + answer (feeds W1-01) |
| DISC-05 | Does any test assert that `/api/conversations` or `/api/bookings` responses exclude patient name/phone? | test names (feeds W1-11) |
