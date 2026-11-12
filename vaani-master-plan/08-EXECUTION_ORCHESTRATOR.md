# 08 — EXECUTION ORCHESTRATOR

Audience: the orchestrating agent (or person) who hands packets to implementing agents and merges their work.

## 1. Operating model

- Owner override for Waves 1-2: one continuous implementing agent works directly on a clean `main`, with one commit per packet. It must not begin while the concurrent remediation checkout is dirty, must never discard pre-existing work, and must stage only packet-owned files.
- Every agent receives exactly two documents: `07-AGENT_CONTEXT.md` and its packet. Nothing else.
- The orchestrator never trusts a completion report by itself; it runs the gate in `09-QUALITY_GATES.md` §2 on the branch.
- Merge order inside a chain is fixed. Chains merge independently.

## 2. Wave 1 dependency graph

```
Chain A (app/workers/inbound.py)          W1-01 ─▶ W1-05 ─▶ W1-04 ─▶ W1-10
Chain B (owner_api/routes.py, App.tsx)    W1-06 ─▶ W1-07 ─▶ W1-11 ─▶ W1-12
Chain C (agent prompts/templates)         W1-02
Chain D (slots_get, engine.hold_slot)     W1-03
Chain E (config, main, .env.example)      W1-08
Chain F (Dockerfile)                      W1-09
Chain G (relative_date.py)                W1-13

All chains ──▶ INT-1 (integration checkpoint) ──▶ Wave 2
```

**Critical path:** Chain A (4 sequential tasks, one of them Medium) ≈ Chain B (4 sequential, two Medium). Everything else is off the critical path. Start A1, B1, C, D, E, F, G together on day one.

### File ownership (prevents conflicting parallel edits)

| File | Owned by | Notes |
|---|---|---|
| `app/workers/inbound.py` | Chain A only | W1-08 is explicitly forbidden from touching it |
| `app/channels/whatsapp.py` | W1-04 only | additive function |
| `app/channels/voice/session.py` | W1-01 only | one line |
| `app/owner_api/routes.py`, `app/owner_api/views.py` | Chain B | |
| `dashboard/src/App.tsx` | W1-06 (one expression) then W1-12 | sequential |
| `app/agent/nodes/*`, `app/agent/templates/*` | W1-02 only | |
| `app/agent/tools/slots_get.py`, `engine.py::hold_slot` | W1-03 only | |
| `app/config.py`, `app/main.py`, `.env.example`, `tests/conftest.py` | W1-08 only | |
| `Dockerfile` | W1-09 only | |
| `app/booking/relative_date.py` | W1-13 only | |
| `app/booking/timefmt.py` | created by W1-05; read by W1-04, W1-11 | W1-11 inlines the timezone lookup if its base lacks the file |

**Known soft overlap:** W1-03 and W1-04 may both edit fixtures in the same test files (slot dates vs cancel flow). Merge W1-03 first if both are ready; the later one rebases.

## 3. Agent assignment

| Tier | Tasks | Why |
|---|---|---|
| Small / inexpensive model | W1-01, W1-05, W1-10, W1-06, W1-07, W1-03, W1-09, W1-13 | single objective, exact instructions, pure or near-pure functions |
| Medium | W1-04, W1-11, W1-12, W1-02, W1-08 | multi-file, state handling, mock coupling, or security guard |
| Advanced (reserve) | W2-02, W2-03, W2-06 and any escalation | design judgment required |
| Read-only discovery (small/medium, 1 h cap) | DISC-01…05 | run on day one in parallel; results attach to W1-08, W1-03, W1-01, W1-11 |

One agent per chain is more efficient than one per task for chains A and B **if** the agent's context is reset between tasks (fresh session, same branch lineage). Do not let an agent carry assumptions from one packet into the next.

**Do not** create separate backend/frontend/security/QA agents for Wave 1. The work is small; role specialization would add hand-offs without adding reliability. The only cross-role hand-off is W1-11 → W1-12, and its contract is the response shape written in both packets.

## 4. Stable contracts fixed before dependents start

| Contract | Defined in | Consumed by |
|---|---|---|
| `strip_citations(text) -> str` | W1-01 | Wave 2 flows |
| `format_local(instant, tz) -> str`, `tenant_timezone(tenant)` | W1-05 | W1-04, W1-11 |
| Reply ids `cancel:confirm`, `cancel:keep`; `conversation.cancel_flow` | W1-04 | W2-01, W2-08 |
| Error body `{"detail": {"code", "message"}}` | W1-06 | W1-12 and all later routes |
| Conversation/booking view-model fields | W1-11 | W1-12, W3-02 |
| `ENABLE_VOICE/PAYMENTS/BILLING` | W1-08 | deployment, W2-07 |

If an implementing agent proposes changing one of these, that is an escalation, not a deviation to accept.

## 5. Integration checkpoints

**INT-1 (after all Wave-1 chains merge)** — run by the orchestrator on `main`:
1. Full gate (09 §2).
2. Scripted transcript under mock adapters (extend `tests/test_two_clinic_whatsapp_acceptance.py` or add `tests/test_wave1_transcript.py`): two tenants with different names; FAQ → reply contains the right clinic name and no `[source_ref`; "book tomorrow" → picker with no past slot; pick → confirm → booked; "status" → local-time string; "cancel" → buttons → `cancel:confirm` → cancelled; an audio message → the unsupported reply.
3. Build the image; boot it with `APP_ENV=staging`, flags off, only WhatsApp + LLM + datastore secrets set to dummy-but-valid values; `/health` is 200 and `/webhooks/exotel` is 404.
4. Record: commit SHA, image digest, test counts. One paragraph, appended to a single `docs/decision-log.md` (create it; this replaces further additions to the remediation ledger).

**INT-2 (after Wave 2)** — real-model eval at thresholds; golden transcripts in four languages; 20-conversation concurrency soak.

**INT-3 (pilot gate)** — live staging smoke on a real WhatsApp test number (script in 09 §6).

## 5a. Wave 2 execution order

```
W2-04 ─┬─▶ W2-05 ─▶ W2-01 ─┬─▶ W2-03 ─▶ W2-08 ─▶ W2-09 ─▶ W2-06 ─▶ W2-07 ─▶ INT-2
       └─▶ W2-02 ──────────┘
            (baseline real-model run recorded before W2-03 merges)
```

| Step | Task | Tier | Gate before the next step |
|---|---|---|---|
| 1 | W2-04 LLM client | Medium | task gate |
| 2a | W2-05 observability | Small | owner approved `sentry-sdk`; task gate |
| 2b | W2-02 real-model eval (after 2a in the single-agent run) | Advanced for the dataset; Medium for the harness | harness tests pass; credentialed baseline is recorded as pending because no provider credential or prescribed model is available |
| 3 | W2-01 localization | Medium | task gate; `docs/i18n-review.md` handed to a native speaker (review may finish later, must finish before the pilot) |
| 4 | W2-03 understand | Advanced | task gate + independent review; before/after real-model reports remain an external acceptance gate and block INT-2/pilot readiness, not implementation |
| 5 | W2-08 golden transcripts | Medium | zero unexplained `xfail` |
| 6 | W2-09 menu | Medium | golden transcripts still green |
| 7 | W2-06 concurrency | Advanced | task gate + independent review + CI kill-tests |
| 8 | W2-07 scheduler | Medium | task gate; release note "start the scheduler service" |

**Why sequential:** W2-05, W2-01, W2-03, W2-09, W2-06 and W2-07 all edit `app/workers/inbound.py`. Running them in parallel would cost more in conflict resolution than it saves. W2-06 goes late on purpose: it restructures the consumer loop, and every earlier task is easier to verify on the simple serial loop.

**Recorded owner inputs (12 November 2026):** `sentry-sdk>=2` is approved and the section 5 eval thresholds are ratified. No model identifiers are prescribed and no OpenRouter key is available. Implement all packets without pausing for credentials, but leave the W2-02 real run, W2-03 comparison, INT-2, and pilot readiness pending. Native Hindi/Odia and dataset review follows implementation and remains mandatory before the pilot.

**Review checklists for the two high-risk Wave 2 changes** (in addition to 09 §4):
- **W2-03:** `scope_gate` still precedes every route to `responder`; no new edge into `responder` for medical / out-of-scope / abuse / complaint; the model's date is range-validated before use; `User message: '…'` is the last line of the classifier prompt; voice still reaches the responder.
- **W2-06:** two handlers can never run at once for the same patient key; every exception path releases the lease; `WORKER_CONCURRENCY=1` reproduces the old behaviour; duplicate deliveries are still processed once; heartbeat keeps updating during a long batch.

## 6. Handling failures

| Situation | Orchestrator action |
|---|---|
| Agent reports success but the gate fails | Return the failing output verbatim to the **same** agent once. Second failure → reassign to the next tier with the packet + the two failure logs. |
| Agent stops with an escalation | Read the cited code yourself. If the packet's premise is wrong, fix the packet (and this plan), then reassign. Never tell the agent to "work around it". |
| Agent changed files outside its packet | Reject the PR. Ask for a minimal re-do; do not cherry-pick. |
| Agent weakened or deleted a test assertion | Reject, unless the packet explicitly authorised rewriting that test (W1-04 one-step-cancel tests; fixture dates in W1-03; flags in W1-08). |
| Merge conflict between chains | The later PR rebases. If the conflict is in a file the ownership table assigns to someone else, one of the agents violated scope — find which. |
| Unexpected architectural finding (e.g. a second place that sends patient text) | Pause the affected chain, add the finding to `02`, issue a revised packet. Cap: one advanced-model consultation per finding. |
| Three consecutive escalations in one chain | Stop the chain; have an advanced agent re-read the files that chain touches and rewrite its remaining packets against current code. |

**Retry budget:** two attempts per packet per tier; then escalate a tier. A small-tier agent should never spend more than ~40 tool calls on a Small packet — past that it is lost; stop it.

## 7. Cost controls

1. **Cheap models first** for the eight Small tasks; they are specified to the line.
2. **No repository tours.** Agents open only the files in "Files to Inspect". The context file removes the need to read docs.
3. **Batch the tiny ones:** W1-06 + W1-07 may be given to one agent in one session (same file, both Small) — still two commits.
4. **Automated checks replace AI review** for: lint, types, tests, tenant-isolation grep, literal scan (`test_no_tenant_literals`), mock eval, dashboard build. Use an AI reviewer only for the three high-risk diffs listed in 09 §4.
5. **Write decisions once:** D1–D7 outcomes go into `docs/decision-log.md` and into `07-AGENT_CONTEXT.md` so no later agent re-derives them.
6. **Wave 2 packets exist but pre-date Wave 1's implementation.** Budget five minutes per packet to check its "Repository Context" against merged code before assigning it. Do not pre-write Wave 3–4 packets; write each when its dependencies have merged (one advanced-model session per wave).
7. **Escalate early:** an agent that hits an escalation condition should stop at once; a stalled cheap agent costs more than a ten-minute expert look.

## 8. Day-by-day plan for Wave 1 (indicative)

| Day | Parallel work |
|---|---|
| 1 | DISC-01…05 · A1 (W1-01) · B1+B2 (W1-06, W1-07) · C (W1-02) · D (W1-03) · E (W1-08) · F (W1-09) · G (W1-13) |
| 2 | A2 (W1-05) → A3 (W1-04) · B3 (W1-11) |
| 3 | A4 (W1-10) · B4 (W1-12) |
| 4 | INT-1, fixes, decision log; owner reviews D1–D7 |

Human-side tasks H-01…H-05 (05) run in parallel from day 1; they, not the code, set the date of the pilot.
