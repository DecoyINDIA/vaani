# Vaani production readiness review

**Review date:** 6 November 2026, Asia/Kolkata
**Verdict:** Not ready for production
**Implementation status:** All findings below remain open
**Execution plan:** [Production remediation plan](production-remediation-plan.md)

Vaani has working scaffolding and passing offline checks, but the customer booking, staff handoff, voice, and payment journeys are not complete. Production deployment must wait for the applicable release gates in the remediation plan. Earlier implementation summaries describe work performed; they are not evidence that these journeys work against live providers.

## Scope and baseline

The review covered the 43 non-empty application Python files, the React dashboard, tests, evaluation harness, CI, Docker configuration, operational scripts, and supporting specifications. It traced authentication, tenant boundaries, inbound processing, scheduling, booking, handoff, payments, voice, outbound delivery, and patient deletion.

The checkout started at `b2aee5e85655987b3386c78bd93f019768740630`. Concurrent changes appeared in `Dockerfile`, `app/models/collections.py`, `app/owner_api/routes.py`, the three worker files, and the removal of `ops/healthcheck.sh`. Those changes were re-read; the final Python checks ran against the resulting working tree. Findings therefore apply to that working tree, not solely to the named commit. The reviewer made no application changes.

Local Python was 3.14.5; CI and Docker target Python 3.12. Tests and reproductions used isolated mock MongoDB data and mocked provider responses. No real patient data or live provider sends were used. Local package/build results do not prove the Docker image or deployed environment works.

## Verification results

| Check | Observed result | Limit |
| --- | --- | --- |
| `python -m pytest -q` | 28 passed, 1 skipped | The skipped test is the broader tenant-route probe; existing coverage does not exercise complete production journeys |
| `python -m ruff check .` | Passed | Static checks only |
| `python -m mypy app` | Passed across 56 source files | Static checks only |
| `python evals/run_evals.py --ci` | 25 of 25 cases passed | Rule-based mock LLM; not model quality or real multilingual accuracy |
| `uv build --wheel` | Passed | Package build, not container startup |
| `npm run build` in `dashboard` | Passed | Produces a placeholder dashboard |
| `npm run lint` in `dashboard` | Failed | `'eslint' is not recognized as an internal or external command` |
| Browser against local FastAPI | Placeholder dashboard rendered | No usable login, inbox, or booking UI |
| Docker runtime | Not run | Docker daemon unavailable |
| `pip-audit` against installed environment | 22 reported rows, 19 distinct package/advisory pairs, 9 packages | Duplicate rows removed from the distinct count; exploitability and final image contents need separate triage |

Dependency advisory packages were `certifi`, `cryptography`, `dnspython`, `ecdsa`, `langgraph-sdk`, `pyasn1`, `pymongo`, `python-jose`, and `urllib3`. These are scan findings, not 19 confirmed exploitable application defects. For example, the python-jose asymmetric-key advisory is not the same issue as the default symmetric JWT secret below. Final dependency decisions must use the locked release image and reachable code paths.

## Finding register

IDs R01 through R15 preserve the order of the review's launch blockers. R16 through R20 cover the additional findings. All statuses are **Open**. Severity reflects application impact; configuration findings do not assert that the current host is publicly reachable.

### R01 Default JWT secret accepted in production

**Critical — CONFIRMED.** [Settings](../app/config.py), [startup](../app/main.py), [JWT verification](../app/owner_api/auth.py).

`jwt_secret` defaults to `changeme`, and production startup does not reject it. With other required settings populated, production startup succeeded. A token signed with the default secret accessed the selected tenant's settings with HTTP 200. Verification also does not require a valid active user membership.

Required outcome: reject insecure production configuration and enforce token purpose, expiry, identity, membership, and role at the owner API boundary.

### R02 Unauthenticated Exotel endpoint mints stream tokens

**Critical — CONFIRMED.** [Exotel gateway](../app/gateway/exotel.py), `receive` and `missed_call`.

An unauthenticated POST containing a known clinic number and arbitrary call ID returned a signed stream URL even with a non-default signing secret. The WebSocket token therefore does not authenticate the source of the call. The missed-call endpoint also performs writes and sends without authenticating the originating request.

Required outcome: authenticate provider ingress before issuing call authorization or producing side effects. Bind stream authorization to a verified call, tenant, caller, and bounded lifetime.

### R03 MongoDB identifiers break normal operations

**High — CONFIRMED.** [Accessors](../app/models/base.py), [owner routes](../app/owner_api/routes.py), [booking engine](../app/booking/engine.py), [slot lookup](../app/agent/tools/slots_get.py).

MongoDB generates `ObjectId` values, but callers stringify IDs and later compare those strings directly against `_id`. Owner endpoints also return raw MongoDB documents. A normally created conversation caused HTTP 500 on listing; takeover returned HTTP 200 without changing its state; a generated slot was offered but could not be held. Booking confirmation discards the inserted booking ID, so the create tool returns an empty ID even with string fixtures.

Required outcome: consistent stored references, explicit API serialization, validated ID conversion, accurate not-found responses, and returned inserted IDs.

### R04 Agent booking journeys do not execute mutations

**High — CONFIRMED.** [Tool router](../app/agent/nodes/tool_router.py), [inbound parser](../app/workers/inbound.py).

The router calls FAQ retrieval and slot lookup only. Booking creation, cancellation, rescheduling, and payment-link creation are not invoked. `booking_status` queries availability instead of the patient's existing booking. Non-text button/list replies are skipped by inbound processing.

Required outcome: authenticated patient context, persisted multi-turn selection and confirmation, real booking mutations, patient-scoped status lookup, and supported interactive reply parsing.

### R05 Human handoff does not reliably transfer control

**High — CONFIRMED.** [Scope gate](../app/agent/nodes/scope_gate.py), [conversation resolution](../app/workers/inbound.py), [escalation tool](../app/agent/tools/escalate.py).

`human_request` falls through without escalation. Conversation resolution searches for `state="open"` only, while handoff uses `human` and return uses `bot`. A new message after a manually established human handoff created a new bot conversation. Escalation writes records but does not send a staff alert. R03 separately prevents many state updates from matching generated IDs.

Required outcome: one consistent conversation state machine, explicit human-request routing, bot suppression while staff owns a conversation, reliable staff notification, and audited return with context.

### R06 Voice transport and TTS violate provider contracts

**High — CONFIRMED.** [Exotel socket](../app/gateway/exotel.py), [TTS adapter](../app/channels/voice/tts.py), [voice tests](../tests/test_voice.py).

The socket expects binary `QUERY:` and `DTMF_` test commands. Sending the documented Exotel JSON `connected` event closed the socket with a missing `bytes` error; ordinary audio has no transcription dispatch path. The TTS adapter reads `audio_encoded`, whereas Sarvam's documented successful response contains `audios`; a representative response decoded to zero bytes. Tests exercise synthetic commands instead of provider event envelopes.

Required outcome: real provider event parsing, PCM buffering/transcription, correctly encoded outbound media, validated TTS responses, real interruption behavior, and provider sandbox call evidence.

### R07 Voice callers share identity and consent

**High — CONFIRMED.** [Stream URL construction](../app/gateway/exotel.py), [voice session](../app/channels/voice/session.py).

The generated URL omits caller identity. Session initialization substitutes `unknown_phone` and looks up contacts by that value. Two distinct calls reused one contact and inherited its granted consent and active conversation.

Required outcome: derive identity from authenticated call metadata; unidentified callers must never merge into a shared patient. Persist consent against the actual caller and notice version.

### R08 Queue recovery can permanently lose messages

**High — CONFIRMED.** [Deduplication](../app/gateway/middleware.py), [webhook enqueue](../app/gateway/meta.py), [worker](../app/workers/inbound.py), [message accessors](../app/models/collections.py).

A reservation placeholder is treated as an already-seen message. If execution stops before enqueue, the next delivery is discarded. The fallback consumer clears queue status before the WhatsApp send; injecting a send failure incremented retries but left the message outside the queued set. If both enqueue stores fail, the webhook returns HTTP 200 with `critical_failure`. Redis-only payload storage also conflicts with the restore runbook's claim that Redis is rebuildable.

Required outcome: durable receipt before acknowledgment, reclaimable processing leases, independently recoverable outbound work, and explicit handling of ambiguous provider delivery.

### R09 Outbound WhatsApp is not tenant aware and can fake success

**High — CONFIRMED.** [WhatsApp channel](../app/channels/whatsapp.py), [production configuration checks](../app/main.py).

Every tenant uses the same global sender-number ID and access token. Replies for additional clinic numbers therefore use the configured sender. When the number ID is absent, the sender returns mock success even in production; startup only checks the access token.

Required outcome: tenant-bound outbound credentials and sender IDs, complete startup/onboarding validation, and explicit test-only mocks.

### R10 Payment links and paid events are not production functional

**High — CONFIRMED.** [Razorpay webhook](../app/gateway/razorpay.py), [payment-link tool](../app/agent/tools/payment_link_create.py), [payment test](../tests/test_phase3.py).

The handler checks `payment.link.paid`; the provider sends `payment_link.paid`. A provider-format event returned HTTP 200 while leaving the payment `issued`. The existing test repeats the incorrect event name. The link helper fabricates a URL and identifier without making a provider request; it cannot supply a valid provider-created link when the currently disconnected tool is wired in.

Required outcome: provider-created links, correct signed event handling, amount/currency/reference verification, duplicate-safe reconciliation, and safe late-payment handling for cancelled bookings.

### R11 Owner operating surface is incomplete

**High — CONFIRMED.** [Dashboard](../dashboard/src/App.tsx), [auth module](../app/owner_api/auth.py), [owner routes](../app/owner_api/routes.py), [Dockerfile](../Dockerfile).

The browser shows only a skeleton paragraph. There is no login/refresh endpoint, staff reply workflow, operational inbox, or calendar. The Dockerfile neither builds nor copies the dashboard. JWT helper tests do not establish a usable owner authentication journey.

Required outcome: invitation-bound login/session lifecycle, tenant-scoped operational UI and staff reply API, and static assets included in the tested container.

### R12 Booking transitions leave slot state inconsistent

**High — CONFIRMED for the exposed owner API.** [Booking update route](../app/owner_api/routes.py), [cancel tool](../app/agent/tools/booking_cancel.py), [move tool](../app/agent/tools/booking_move.py).

The owner PATCH endpoint changes only the booking status. Cancelling through it left the slot `booked`. An isolated tool check also showed that cancelling an old booking twice reopens a slot already booked by a different patient. The latter tool is not currently connected to the customer graph; it must be repaired before R04 connects it. Rescheduling performs multiple writes without a transaction or durable recovery.

Required outcome: shared guarded booking transitions, replay safety, current booking ownership on slots, and atomic or recoverable updates across records.

### R13 Failed reminders are recorded as delivered

**High — CONFIRMED.** [Reminder worker](../app/workers/reminders.py), [template definitions](../ops/whatsapp_templates.md).

A send exception is logged, then `reminders_sent` is updated anyway. An injected provider failure marked the 24-hour reminder sent. Template variables also disagree with the documented pack: the 24-hour reminder needs four values but receives three, while the 2-hour reminder receives booking ID and ISO timestamp in place of time and landmark.

Required outcome: successful-send tracking, retryable failed delivery, deduplication across workers, and parameters validated against the actual approved templates.

### R14 Grounding gate accepts invented references

**High — CONFIRMED.** [Output gate](../app/agent/nodes/output_gate.py), [evaluation harness](../evals/run_evals.py).

The gate checks for the substring `[source_ref:` without validating the reference or claim. It accepted `The fee is Rs 999999. [source_ref: fabricated]` with no tool facts. Passing evaluation checks for expected tags does not prove factual correctness.

Required outcome: allow only retrieved references, render sensitive structured facts from tool results, validate facts as well as tags, and test production models with adversarial and multilingual cases.

### R15 Patient erasure is unimplemented

**High — CONFIRMED.** [Erasure command](../ops/dpdp_delete.py), [privacy notice](../ops/dpdp_notice.md).

The documented erasure command always raises `NotImplementedError`. It cannot perform the promised cross-collection deletion and audit pseudonymization. The review did not establish legal compliance or verify external provider retention settings.

Required outcome: a verified tenant-scoped erasure workflow, explicit retention exceptions, prevention of queued sends after deletion, and a restore procedure that does not resurrect erased data.

### R16 Redis is published without configured authentication

**High for the deployment configuration — CONFIRMED; public reachability unverified.** [Compose](../docker-compose.yml).

The `6379:6379` mapping binds Redis on host interfaces, and the service has no configured authentication. On a host allowing inbound traffic, external clients can access queue and lock state.

Required outcome: private service networking, no production host port, and staging evidence that external Redis access is blocked.

### R17 Appointment times mix local time and UTC

**Medium — CONFIRMED.** [Schedule generation](../app/booking/engine.py), [reminders](../app/workers/reminders.py), [relative dates](../app/booking/relative_date.py), [weekly summaries](../app/workers/weekly_summary.py).

Schedules store naive clinic wall times, while reminders subtract naive UTC. Indian appointment reminders are shifted by 5 hours 30 minutes under that interpretation. Host-local `date.today()` and scheduler time also affect the clinic day. The parser resolves `day after tomorrow` as tomorrow because the shorter keyword is matched first.

Required outcome: tenant timezone, UTC storage for instants, local calendar interpretation, and boundary tests independent of host timezone.

### R18 No recurring slot replenishment

**Medium — CONFIRMED.** [Seed script](../ops/seed_tenant.py), [scheduler](../app/workers/inbound.py), [schedule engine](../app/booking/engine.py).

The only production-code caller of schedule expansion is the demo seed script, which creates a 14-day horizon. No recurring job extends it. The advertised YAML onboarding command also ignores its path and seeds hardcoded demo data.

Required outcome: idempotent rolling slot generation and validated tenant onboarding that cannot silently overwrite demo or unrelated tenant data.

### R19 Billing plan mapping and usage integration are missing

**Medium — CONFIRMED.** [Subscription webhook](../app/gateway/razorpay.py), [invoice calculation](../app/billing/invoice.py), [usage counters](../app/billing/meters.py).

The webhook stores provider plan IDs, but invoice calculation recognizes only the literal `pro`. A `plan_pro` activation produced a Starter base amount of 2999. Usage recording has no production callers, and invoice generation is not scheduled. Invoice code also substitutes a sample GSTIN if configuration is absent. Product pricing documents and the invoice constants need one agreed price source.

Required outcome: explicit provider-to-product plan mapping, actual usage integration, durable invoice identity and issuance, configured billing identity, and one canonical pricing definition. This review does not validate tax treatment.

### R20 CI does not prove release readiness

**Medium — CONFIRMED.** [CI](../.github/workflows/ci.yml), [tests](../tests), [evals](../evals/run_evals.py), [Python manifest](../pyproject.toml), [dashboard manifest](../dashboard/package.json).

CI installs floating dependencies rather than the committed Python lock. There is no committed dashboard lock, frontend lint cannot run, and no real-provider contract, full tenant-route, transaction race, restore, or image-startup gate establishes production behavior. The commented nightly race suite is not implemented in the shown workflow. Dependency advisories require release-image triage rather than treating the installed development environment as the deployed artifact.

Required outcome: reproducible dependencies, behavior-focused regression tests, real datastore integration, provider contract fixtures, separate real-model evaluation, frontend checks, and tested image promotion.

## Reproduction observations

These observations were produced by isolated review scripts; those scripts were not committed as regression tests. The remediation plan requires durable tests that first reproduce each defect and then pass after the fix.

| Probe | Actual result before fixes |
| --- | --- |
| Production startup with default JWT secret | Startup succeeded |
| Forged default-secret token requesting tenant settings | HTTP 200 |
| Unauthenticated Exotel request with arbitrary call ID | HTTP 200 and signed stream token |
| List normally created conversation | HTTP 500 |
| Take over normally created conversation | HTTP 200; stored state remained `open` |
| Next message after human takeover | New bot conversation created |
| Hold generated slot returned by slot lookup | `False` |
| Returned confirmed booking contains inserted ID | `False` |
| Explicit request for a human escalates | `False` |
| Fabricated citation with no facts | `regenerate=False` |
| Fallback reply after injected send failure | No longer queued; retries incremented |
| Repeat cancellation after another patient rebooks | Slot reopened |
| Real `payment_link.paid` event | HTTP 200; payment remained `issued` |
| Two voice calls without caller metadata | Same contact and inherited consent |
| Sarvam response containing `audios` | Zero decoded bytes |
| Exotel JSON `connected` event | WebSocket closed |
| Retry after only reserving a message ID | Rejected as already seen |
| Reminder after injected provider failure | Marked `24h` sent |
| Production outbound with missing sender number ID | Mock success |
| Owner cancellation | Slot remained `booked` |
| Provider `plan_pro` activation followed by invoice | Starter amount 2999 |
| `day after tomorrow` on 6 November 2026 | 7 November rather than 8 November |

## Provider references

Contracts were consulted during the review. Recheck supported models and provider account configuration when implementing; representative fixtures do not replace sandbox validation.

- [Exotel AgentStream WebSocket protocol](https://developer.exotel.com/docs/agentstream/websocket-protocol)
- [Sarvam text-to-speech REST contract](https://docs.sarvam.ai/api-reference/text-to-speech/convert)
- [Razorpay payment-link webhook events](https://razorpay.com/docs/webhooks/payment-links)

## What to preserve

Keep explicit tenant-scoped accessors, signed Meta/Razorpay webhook verification, atomic slot acquisition, and graph routing to static medical-refusal responses. Complete and test the boundaries around these foundations rather than replacing the application architecture.

## Limits of the conclusion

The review did not execute live paid transactions, real telephone calls, production LLM quality tests, a Docker deployment, a backup restore, a load test, or an infrastructure/security audit of a live host. Provider approvals, business validation gates, real deployment secrets, and legal/tax sign-off were not verified. These remain explicit release prerequisites where applicable.
