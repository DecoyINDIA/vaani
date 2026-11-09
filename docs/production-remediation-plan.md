# Vaani production remediation plan

**Created:** 6 November 2026, Asia/Kolkata
**Last reconciled:** 9 November 2026, Asia/Kolkata; repository `6fcd7e8`, implementation `e3c1205`
**Status:** Implementation and CI milestones completed below; all R01–R20 final closures remain pending
**Release decision:** No go
**Evidence:** [Production readiness review](production-review.md)

This plan closes all 20 findings from the production review and defines how to prove the repaired product works. It covers the existing WhatsApp, voice, owner dashboard, and billing scope. It does not authorize deployment or external customer communications. The prior product and engineering plans remain requirements references; this plan takes precedence for remediation order and production-readiness claims.

## Execution rules

### Brief for any agent taking over

Read this plan, the completion ledger, repository instructions, and the current checkout before working. Execute the remaining work packages below in dependency order. Preserve other contributors' changes. Complete one reviewable package at a time, run its required checks, update this plan with the exact evidence and remaining gaps, then **commit with a sensible descriptive message and push to GitHub `origin/main` after every work package**. Verify that the remote main contains the commit and inspect its required GitHub Actions results before starting the next dependent package. A local commit alone is not a completed handoff. Never force-push main. If main advances, integrate its changes safely and rerun affected checks before pushing. If a check fails, fix it and push the correction; record the failure and replacement evidence. Do not leave several completed packages waiting for one final push.

Record the implementation SHA and workflow URL after each package; a follow-up evidence-only documentation commit must also be pushed. Keep credentials and patient data out of commits. If a package needs unavailable credentials, an approved business decision, staging access, or an independent reviewer, record the exact pending input and continue independent work. Do not invent provider success, infer approval, or close a finding from mock tests. This brief authorizes implementation and main updates; deployment and customer communications still require their existing separate authority.

Use **Complete** for a deliverable whose stated scope has recorded proof, and **Pending** for unfinished or unverified work. A completed local implementation does not complete its provider/staging acceptance. The ledger's historical `In progress` entries mean **Pending final closure**; `Verified` is reserved for full acceptance with independent review. No finding is currently Verified.

1. Keep one application, the existing datastore stack, and small reviewable changes. Do not add a general workflow engine, replacement framework, or unrelated redesign.
2. Add the smallest meaningful regression for each failure before changing its behavior. Use real MongoDB and Redis for transactions, leases, indexes, and concurrent delivery; mocks alone cannot establish those guarantees.
3. Start from the current checkout and preserve concurrent work. Record the exact reviewed commit and pending changes before implementation; do not revert the seven existing non-documentation changes merely to recreate the review baseline.
4. Default every finding to Open. Close it only when its acceptance criteria and evidence are recorded in the completion ledger. A mock evaluation or successful build cannot close an integration finding.
5. Keep provider credentials and patient data out of fixtures, logs, screenshots, and documentation. Use synthetic fixtures and sandbox accounts for regression work.
6. Promote the tested container digest. Use a staged rollout only after the release gates pass. No calendar launch date is committed until provider access, the migration inventory, and the first implementation package are complete.

### Execution baseline — 7 November 2026

- Implementation started from commit `b2aee5e85655987b3386c78bd93f019768740630` (`docs: record review-remediation work in handoff and memory docs`).
- Pre-existing tracked changes were preserved in `06-engineering-plan.md`, `Dockerfile`, `README.md`, `app/models/collections.py`, `app/owner_api/routes.py`, `app/workers/inbound.py`, `app/workers/reminders.py`, `app/workers/weekly_summary.py`, `docs/handoff.md`, `docs/memory.md`, and the deleted `ops/healthcheck.sh`. The review and this plan were untracked. Remediation edits are layered onto that dirty checkout; no baseline change was reverted.
- Pre-change local evidence: `pytest -q` 28 passed and 1 skipped; Ruff and mypy passed; dashboard build passed; dashboard lint failed because ESLint was not installed. Docker image verification was unavailable because the local Docker Desktop engine was not running.
- Historical baseline only: at that point work was uncommitted and had no independent reviewer. The implementation is now committed through `e3c1205` and evidence documentation through `6fcd7e8`; the reconciliation checkout was clean. Independent review and the outstanding acceptance work below remain pending.

## Current status — 9 November 2026

The latest recorded required [CI run 42595910578](https://github.com/DecoyINDIA/vaani/actions/runs/42595910578) was rechecked through GitHub and is **Complete / successful**, verifying commit `9b6d76ff416286e07daa9ec63f46c6d78fadf92c` over implementation commits `0baff57b019b840cf098199b0c03478985c49091` and `e3c1205bb64d96f5fc3ebd39a3608b43039c72fa`. Candidate digest `sha256:0222ea7c34526eec65b621620f6ac2317b18d9d7714860e85cdbbe88465e7104` was published under tag `candidate-9b6d76ff416286e07daa9ec63f46c6d78fadf92c-42595910578-1`. This is the verified implementation baseline, not a production release approval.

### Completed deliverables

- [x] **Complete — reproducible development/CI foundation:** locked Python/Node installs, Python quality/type checks, wheel/dashboard build and lint, tenant-isolation checks, dependency audits, and sanitized mock-evaluation artifacts are committed and exercised by required CI.
- [x] **Complete — current offline regression gate:** 124 tests passed, with 4 environment-dependent skips; 25/25 mock evaluations passed. Skips and mock scores do not prove real-provider or real-model behavior.
- [x] **Complete — real MongoDB transaction evidence:** required replica-set rollback and 500-concurrent-slot-claim tests pass with one winning booking and no orphan booked slot for the tested fixtures, plus real replica-set transactions for generated ObjectId booking/move/cancel lifecycle.
- [x] **Complete — synthetic recovery evidence:** backup/restore, Redis rebuild, restored erasure suppression, and exact-image process-kill recovery checkpoints pass in CI. Ambiguous interrupted sends remain visible and are not blindly retried.
- [x] **Complete — tested candidate publication:** CI built and passed API/worker/dashboard/webhook/crash smoke and the fixed High/Critical Trivy gate, and published `ghcr.io/decoyindia/vaani@sha256:0222ea7c34526eec65b621620f6ac2317b18d9d7714860e85cdbbe88465e7104`. No release promotion or deployment is established by this result.
- [x] **Complete — recorded local implementation milestones:** authentication/session/role checks; durable inbound/outbound work and operator issue views; shared guarded booking transitions; persisted interactive booking and handoff; owner dashboard journeys; tenant routing and scheduling; voice/payment contracts; billing issuance; deletion/inventory/onboarding tools; grounded retrieval contracts; real handoff on classifier/responder failure; and end-to-end generated ObjectId boundaries across booking, payment, reminder, and owner APIs with ambiguous collision rejection and cross-tenant isolation. The ledger records the scope and limits for each. These milestones do not establish full acceptance of their findings.

### Pending final acceptance

| Findings | Status | Remaining proof or implementation |
| --- | --- | --- |
| R01, R16 | Pending | Production-mode startup/session/rotation checks and private-network proof in staging; independent review |
| R02, R06, R07 | Pending | Verified Exotel ingress/proxy calls, two-caller isolation and consent, supported production voice configuration, audio/interruption and latency evidence |
| R03, R17 | Pending | Generated-ID coverage across all API/tool paths, reference integrity, production-backup inventory, timestamp decisions, resumable backfill and interrupted-run proof |
| R04, R05, R09, R12, R13, R18 | Pending | Two-clinic real WhatsApp journeys, actual template approval match, measured handoff/SLA/alert delivery, onboarding rehearsal, and broader booking/topology coverage |
| R11 | Pending | Authenticated staging browser journeys on desktop/mobile, Atlas-backed KB read/write behavior, server-side roles and delivery/processing issue visibility |
| R10, R19 | Pending | Razorpay sandbox journey/reconciliation, approved prices and billing identity/GST/SAC decisions, invoice rendering/delivery and provider usage reconciliation |
| R14 | Pending | Approved models/secrets, provisioned Atlas indexes, credentialed retrieval accuracy and full multilingual real-model release thresholds |
| R15 | Pending | Retention approval, provider deletion, external erasure-ledger operation and timed staging restore |
| R08, R20 and release | Pending | Configured alert drill, broader load, real provider/model gates, timed RTO/RPO, independent review, operator release record and authorized promotion |

The identifier audit is unfinished: booking slot/contact and payment-reference boundaries need generated-ObjectId regression coverage before R03 can close. No code change for that follow-up is included in this documentation update. The credentialed retrieval workflow exists, but required Actions secrets and approved model/index variables have not been established in the recorded evidence. Local Docker trouble in the historical changelog is superseded for CI image build/scan by successful Linux CI; it must not be presented as a current blocker to those completed gates.

## Ownership and prerequisites

These are required roles, not assignments to people. Assign actual owners when implementation begins.

| Responsibility | Required role | First deliverable |
| --- | --- | --- |
| API, data, booking, durable work | Backend implementer | R01/R03 failing regression tests and data inventory |
| WhatsApp, voice, payment contracts | Integration implementer | Sanitized official payload fixtures and sandbox account configuration |
| Login and operating dashboard | Frontend implementer | Existing user-flow checklist mapped to endpoints |
| Independent verification | Reviewer | Challenge failure cases and inspect closure evidence |
| Containers, credentials, recovery | Deployment operator | Staging replica set, Redis, secret inventory, restore target |
| Product and billing decisions | Product owner | Canonical prices, enabled release scope, staff recipients |
| Retention and billing policy | Responsible business owner with advisers as needed | Documented retention exceptions and billing identity |

One person may fill multiple implementation roles. Record the reviewer explicitly. Provider prerequisites must be tracked as blocked integration work, not replaced by synthetic success.

Required external inputs are Exotel's supported authenticated ingress/call-verification mechanism, tenant-specific WhatsApp sender credentials and approved templates, STT/TTS credentials and supported models, a Razorpay sandbox and product-plan mapping, invited owner/staff identities, and staging infrastructure. Collect these while the independent local fixes proceed.

### External input and prerequisite register

Every external input required for full R01–R20 closure is tracked below. Local development, baseline regressions, and data/ID boundary hardening (WP01–WP02) proceed independently of pending external credentials.

| Prerequisite / external input | Category | Status | Responsible role | Next action / exit requirement |
| --- | --- | --- | --- | --- |
| Exotel Basic-authenticated Call Details & AgentStream ingress | Provider access | Pending | Integration implementer | Configure sandbox Exotel account, SID/token, and verify Call Details API callback against proxy |
| Meta WhatsApp Cloud API credentials & sender mappings (2 clinics) | Provider access | Pending | Integration implementer | Configure 2 sandbox WABA tenant accounts, sender IDs, and test phone numbers |
| Sarvam STT (Saaras v4) and TTS (Bulbul v3) API key | Provider access | Pending | Integration implementer | Obtain API credentials, configure language/speaker combinations, and run live sandbox audio tests |
| Razorpay sandbox API key & secret | Provider access | Pending | Integration implementer | Configure test API credentials, product plans, and verify `payment_link.paid` signature handling |
| Staging MongoDB replica set (`VAANI_INTEGRATION_MONGODB_URI`) | Staging infrastructure | Pending | Deployment operator | Provision 3-node replica set, configure private VPC, and run replica-set race suite |
| Staging private Redis (no host port publication) | Staging infrastructure | Pending | Deployment operator | Deploy isolated Redis in staging compose network; prove API and worker communicate privately |
| Staging restore & timed recovery target | Staging infrastructure | Pending | Deployment operator | Prepare staging restore volume; measure and record RTO ≤15m and RPO ≤1h on representative snapshot |
| Staging TLS reverse proxy / ingress domain | Staging infrastructure | Pending | Deployment operator | Set up public HTTPS endpoint for incoming provider webhooks (Exotel & WhatsApp) |
| Approved LLM models & OpenRouter API key | Models & search | Pending | Product owner / Backend implementer | Ratify production classifier and responder models; configure `OPENROUTER_API_KEY` for evaluation |
| Approved embedding model & OpenRouter key | Models & search | Pending | Product owner / Backend implementer | Approve `text-embedding-3-small` (1536d) or equivalent; configure credentials for retrieval eval |
| Provisioned Atlas Vector & Text Search indexes | Models & search | Pending | Deployment operator / Backend implementer | Create `kb_vector_index` and `kb_text_index` on staging Atlas database with tenant filters |
| Approved Meta WhatsApp template exports | Provider templates | Pending | Product owner / Integration implementer | Export actual approved template definitions (24h/2h reminder, staff alert, weekly summary, bridge) |
| Invited owner & staff identities (test clinics) | Identity & access | Pending | Product owner / Frontend implementer | List invited owner/staff email and phone identities for Dr. Priya Sharma and staff members |
| Independent verification reviewer appointment | Governance | Pending | Responsible business owner | Formally appoint independent reviewer to challenge R01–R20 acceptance criteria and inspect closures |
| Canonical pricing catalog & feature quotas | Business decision | Pending | Product owner | Resolve and ratify canonical tier prices and quotas across Starter, Growth, and Pro plans |
| Billing legal identity, GSTIN, and SAC code | Business decision | Pending | Responsible business owner | Document legal clinic/platform entity name, registered GSTIN, and SAC 998313 classification |
| DPDP retention exceptions & 7-day erasure SLA | Policy decision | Pending | Responsible business owner | Document statutory medical/financial retention exceptions and ratify 7-day erasure workflow SLA |

## Implementation decisions

### Identifier boundaries

Preserve existing primary IDs. For Mongo-generated entities, use `ObjectId` internally and explicit string serialization at HTTP/tool boundaries. Convert incoming generated IDs once in the accessor boundary and validate malformed values. Keep provider IDs and existing deliberate string IDs as their own types; never cast arbitrary tenant or message IDs to `ObjectId`.

Inventory each collection before choosing a backfill. Normalize existing stringified references to the actual stored entity IDs. If legacy string IDs overlap with ObjectId-shaped strings, identify and resolve collisions explicitly rather than silently guessing. Return inserted IDs and inspect matched counts on updates. Add response schemas so nested ObjectIds cannot reach JSON encoding.

### Conversation and booking state

Use `bot`, `human`, and `closed` conversation states consistently; migrate legacy `open` to `bot`. A new inbound message reuses the active conversation; a human-owned thread records inbound text but cannot generate bot replies. Recheck ownership immediately before bot dispatch, and serialize conflicting takeover/send work so a queued response cannot bypass the handoff.

Use one booking service for owner APIs and agent tools. Store slot ownership and request identity. Hold, confirm, cancel, and move require guarded state transitions and patient/tenant authorization. Use MongoDB transactions on the supported replica-set deployment for changes spanning bookings and slots; tests must use that topology. A hold is owned by a particular operation, not by whoever confirms the slot next.

### Durable receipt and delivery

Make MongoDB the durable source of inbound work before returning successful webhook acknowledgment. Redis remains a wake-up/dispatch optimization that can be rebuilt. Record processing state and an expiring lease with atomic acquisition, attempts, and next retry time. Include both the normal and fallback path in one recovery model so duplicate workers cannot independently execute the same work.

Persist outbound intent separately with a stable operation key and states such as pending, sending, sent, unknown, and failed. Complete inbound business processing after its resulting outbound intent is durable; complete delivery only after provider confirmation. Persist provider message IDs when available. If a send may have succeeded but its acknowledgment was lost, reconcile using supported provider evidence or expose it for operator review. Do not promise exactly-once external delivery where the provider does not support it, and do not blindly retry an ambiguous send.

### Time and scheduled jobs

Give each tenant an explicit timezone, defaulting new Indian clinics to `Asia/Kolkata`. Interpret schedules and relative dates in that timezone, store instants in UTC, and localize only for presentation. Run rolling schedule expansion, reminders, weekly summaries, and billing from the existing worker with persistent per-job deduplication. No new scheduler service is required for the pilot.

### Authentication and mocks

Reject default or short JWT secrets and incomplete enabled-channel configuration at API and worker startup. Require production secrets generated from cryptographically secure randomness. Explicitly select mock adapters in tests; dependency presence or a missing credential must never silently select mock MongoDB, LLM, voice, or WhatsApp behavior in staging/production.

Follow the existing magic-link owner/staff user flow: issue login links only to invited active memberships; use short-lived, single-use tokens with a distinct purpose and stored hashed verifier; exchange them for a normal session. Implement expiring access tokens, rotating/revocable refresh sessions, logout, and role checks. Do not place ordinary long-lived access tokens in staff notification URLs. Use secure browser session handling and CSRF protection where cookie authentication applies.

Exotel stream authorization must follow verified provider ingress, use an appropriate dedicated secret or opaque server-side grant, expire, and bind the call and caller. Verify the provider's supported mechanism before implementing it; do not invent a signature format and label it Exotel authentication.

## Ordered implementation packages

Package labels describe intended review units, not existing branches or pull requests. Split a package if needed for reviewability without weakening its exit criteria.

| Package | Deliverable | Findings | Dependencies |
| --- | --- | --- | --- |
| P0 | Regression baseline and reproducible dependency setup | R20 foundation | None |
| P1 | Secret validation, API authorization, private Redis, verified voice ingress | R01, R02, R16; R09 configuration | P0; Exotel mechanism needed only for its ingress closure |
| P2 | ID boundaries, migration, timezone and rolling schedules | R03, R17, R18 | P0; P1 authorization before exposing APIs |
| P3 | Durable inbound/outbound processing and tenant sender routing | R08, R09, R13 | P1, P2 |
| P4 | Complete booking and handoff journeys with grounded replies | R04, R05, R12, R14 | P2, P3 |
| P5 | Owner login, inbox, calendar, settings and bundled dashboard | R11 | P1, P2; integrate P3/P4 behavior before closure |
| P6 | Real voice and payment/billing journeys | R06, R07, R10, R19 | P1–P4; provider sandbox access |
| P7 | Erasure, retention and recovery procedures | R15 | P2, P3; include P6 payment/voice data before closure |
| P8 | Release-image tests, real-model evaluation and staging rehearsal | R20 completion and all release gates | P1–P7 |

The default is sequential execution. UI implementation and provider contract fixture preparation may proceed independently after their interfaces are stable. No partial package closes a finding whose acceptance criteria depend on later work.

### Remaining work packages — executable handoff order

P0–P8 above identify the original scope. WP01–WP12 below divide its **remaining** work into handoffs. All are **Pending** until their exit evidence is recorded. Execute the numbered actions within each row in order. Every row ends with the commit/push/CI checkpoint in the agent brief; that checkpoint is part of the deliverable, including for documentation or evidence packages. If a row is too large, split it into named subpackages, each with its own tested commit and push to main.

| Order / package | Step-by-step work | Dependencies and exit evidence |
| --- | --- | --- |
| WP01 — Confirm baseline and collect inputs | 1. Inspect main, dirty changes and required workflows. 2. Record the current successful implementation SHA and candidate digest. 3. Inventory provider/staging access, approved models, template exports, invited identities, reviewer and business decisions without recording secrets. 4. Assign each missing input to a responsible role. 5. Commit and push the updated input/status record. | Complete: baseline confirmed at `4567c5e`, required CI run 42591587840 passed, candidate digest `sha256:48cb55552b65bb10ad3e55a6976f51163c28691a9594318f2b9ae89767da9056` recorded; explicit input register with 17 tracked items and role owners established. Unblocks WP02. |
| WP02 — Close generated-ID implementation gaps (P2) | 1. Trace every external ID through API/tools, booking, payment, workers and stored references. 2. Add real generated-ObjectId regressions for list/detail/takeover/return/create/cancel/move and payment references. 3. Resolve IDs at shared boundaries while preserving deliberate legacy string IDs and rejecting ambiguous collisions. 4. Verify nested serialization, controlled errors, cross-tenant denial and actual reference targets. 5. Run quality and replica-set tests; commit, push and verify CI. | Complete: commits `0baff57` and `9b6d76f`; required CI run 42595910578 passed; verified candidate digest `sha256:0222ea7c34526eec65b621620f6ac2317b18d9d7714860e85cdbbe88465e7104`. 124 unit/integration tests passed, full route/tool/worker/payment generated ObjectId boundaries verified. Unblocks WP03. |
| WP03 — Inventory and resumable migration (P2) | 1. Verify a restorable production backup and run read-only `ops/migration_inventory.py` on its isolated restored copy. 2. Resolve collision/orphan/time-provenance decisions explicitly. 3. Implement dry-run-first resumable reference/state/time/ownership backfills. 4. Interrupt and rerun; compare counts, tenant isolation and references. 5. Document maintenance/compatibility/rollback steps, commit, push and verify CI. | WP02 plus backup/operator access. Exit: sanitized inventory, approved decisions, migration code and repeatable restore-copy proof; applying to production requires operator authority. |
| WP04 — Provider configuration and authenticated voice (P1/P6) | 1. Validate actual Exotel and Sarvam contracts and enabled models. 2. Configure sandbox ingress/credentials and tenant mappings securely. 3. Exercise authenticated call/missed-call and grant replay/expiry/metadata rejection. 4. Test two callers, consent, returning history, real STT/TTS audio, interruption and cleanup in every enabled language. 5. Record measured latency, fix failures, commit and push evidence/code; verify CI. | WP01 provider inputs; WP02 ID fixes where relevant. Exit: R02/R06/R07 provider evidence and configuration checks, with sanitized call references and measurements. |
| WP05 — Two-clinic WhatsApp and booking acceptance (P3/P4) | 1. Compare template names/languages/variables to actual Meta approvals. 2. Run two-clinic booking/status/cancel/move/repeated-confirm/unavailable-slot journeys and cross-patient/tenant negatives. 3. Exercise reminders, opt-out, missed-call bridges and summaries through each actual sender. 4. Inject provider failure/unknown delivery and confirm committed state, durable intent and operator visibility. 5. Fix gaps; commit, push and verify CI. | WP02; WP03 for migrated-data proof; actual approved WhatsApp sandbox/senders. Exit: database plus provider evidence for R04/R09/R12/R13 paths. |
| WP06 — Handoff, scheduling and operational alerts (P3/P4) | 1. Rehearse onboarding and rolling horizon/holiday changes. 2. Inject human requests, safety/low-confidence triggers and LLM failures. 3. Verify queued-bot silence, staff reply, required summary and return. 4. Measure 30-second staff delivery and 10-minute in-hours owner escalation; exercise out-of-hours behavior. 5. Deliver queue-age/dead-letter/unknown/provider/heartbeat/horizon alerts to the configured destination; commit, push and verify CI. | WP05 messaging setup; staging destination and recipients. Exit: clock-controlled regressions plus measured staging delivery for R05/R08/R18 and operational release gates. |
| WP07 — Billing and payment completion (P6) | 1. Obtain canonical price/plan, billing identity and GST/SAC decisions. 2. Complete invoice rendering/delivery using durable issuance state. 3. Run Razorpay sandbox create/pay/raw-webhook/status journey with replay, mismatch, cancellation and late-payment cases. 4. Reconcile actual Meta/Exotel usage to invoice units/periods and provider plan lifecycle events. 5. Commit, push and verify CI. | WP02 references, WP04/WP05 usage sources, business approval and sandbox account. Exit: R10/R19 sandbox and approved invoice evidence; never use live customer charges. |
| WP08 — Credentialed retrieval and model evaluation (P4/P8) | 1. Obtain approved models and secure credentials; provision documented tenant-filtered Atlas indexes. 2. Run dry-run/backfill and interrupted rerun on synthetic KB data. 3. Run `.github/workflows/credentialed-retrieval.yml` on the frozen retrieval corpus and require top-3 accuracy at least 90%. 4. Run the full real-model multilingual/safety/grounding and provider-failure evaluation against documented thresholds. 5. Retain sanitized model/config/corpus/SHA results; fix failures, commit, push and verify CI. | WP01 approvals and Atlas/model access; shared ID fixes. Exit: measured R14 and real-model R20 evidence; offline 25/25 cannot replace it. |
| WP09 — Staging owner/staff browser acceptance (P5) | 1. Start the tested image with real staging services and invited memberships. 2. Exercise login/expiry/replay/renew/logout/removed membership and desktop/mobile inbox, calendar, settings, KB, escalation, reply/return journeys. 3. Verify paging, duplicate-submit protection and pending/failed/unknown issue views. 4. Prove role/tenant enforcement and Atlas-backed KB persistence; fix failures, commit, push and verify CI. | WP02 and WP05–WP08 behavior/configuration. Exit: authenticated browser evidence and server-state assertions for R01/R11, including image deep links. |
| WP10 — Retention, erasure and timed recovery (P7/P8) | 1. Obtain retention/provider-data policy decisions. 2. Exercise deletion across WhatsApp/voice/payment records and provider deletion obligations. 3. Operate the external erasure ledger. 4. Restore staging, reapply suppression and rebuild Redis; measure RTO ≤15 minutes and RPO ≤1 hour. 5. Record backup IDs, timing, reconciliation and runbook fixes; commit, push and verify CI. | WP03, WP04/WP07 data paths, operator/backup access. Exit: R15 and recovery release evidence on representative staging data, beyond the completed synthetic drill. |
| WP11 — Load, security and independent closure review (P8) | 1. Exercise existing PRD load/latency targets on the supported topology, including 500 claims and queue/provider failure behavior. 2. Verify production-mode API/worker startup, secret rotation, Redis isolation and current image/dependency audits. 3. Have an independent reviewer challenge every R01–R20 acceptance item and inspect evidence. 4. Fix each gap in tested subpackages. 5. Update checkboxes/ledger only where full proof exists; commit, push and verify CI. | Relevant WP02–WP10 evidence and an independent reviewer. Exit: reviewed closure matrix with no unresolved Critical/High finding; incomplete criteria stay Pending. |
| WP12 — Release decision and operator handoff (P8) | 1. Audit every release gate below against the latest code. 2. Select the immutable digest tested for that code; rerun affected gates after any change. 3. Record migration/backup IDs, rollback conditions, pilot tenants and responsible operator/reviewer decisions. 4. Commit and push the release decision/evidence package, verify main and CI. 5. Promote/deploy only with release authority, then execute pilot checks and record results in a further pushed handoff. | WP11 and all release gates. Exit: explicit authorized release/pilot evidence; otherwise retain No go and list exact Pending gates. Candidate publication alone does not complete this package. |

After each package, the handoff entry must state: package ID; Complete/Pending deliverables; implementation SHA; checks and workflow URL; environment and sanitized evidence; remaining inputs/owner; next package; and confirmation that GitHub main contains the work. Preserve the historical changelog below.

### Package execution and handoff log

#### WP01 — Confirm baseline and collect inputs
- **Deliverables:** Complete. Verified main checkout at `4567c5e01d7f99c9ac925228793a951d34f98bfd` with clean working tree. Confirmed passing required GitHub Actions run `42591587840`. Recorded verified candidate digest `ghcr.io/decoyindia/vaani@sha256:48cb55552b65bb10ad3e55a6976f51163c28691a9594318f2b9ae89767da9056`. Established the complete external input and prerequisite register covering 17 provider, staging, model, template, identity, governance, and business decision items with explicit role owners and next actions.
- **Implementation SHA:** `e3c1205bb64d96f5fc3ebd39a3608b43039c72fa` (baseline documentation SHA `4567c5e01d7f99c9ac925228793a951d34f98bfd`).
- **Checks and workflow URL:** [CI Run 42591587840](https://github.com/DecoyINDIA/vaani/actions/runs/42591587840). Local gate: 118 passed (3 skipped), Ruff clean, mypy clean, evals 25/25 passed, dashboard build and lint clean.
- **Environment and sanitized evidence:** GitHub Actions Ubuntu-latest runners, Python 3.12, Node 22, Docker candidate build; no secrets or patient data in repository.
- **Remaining inputs / owner:** All 17 external inputs tracked in the prerequisite register as Pending; assigned to Backend implementer, Integration implementer, Frontend implementer, Deployment operator, Product owner, and Responsible business owner.
- **Next package:** WP02 — Close generated-ID implementation gaps (P2).
- **Remote main status:** Confirmed `4567c5e` is on GitHub `origin/main`.

#### WP02 — Close generated-ID implementation gaps (P2)
- **Deliverables:** Complete. Hardened all generated `ObjectId` vs legacy string boundaries across models (`TenantScoped.resolve_id`, `update_many`, recursive tuple/list serialization in `serialize_mongo`), booking engine (`_booking_id`, `_slot_id`, `_contact_id` resolution, hold, confirm, move, cancel), owner API routes (`GET /conversations/{id}`, `GET /bookings/{id}`, `takeover`, `reply`, `return`, `PATCH /bookings/{id}` with 409 collision rejection and cross-tenant 404/403 denial), agent tools (`payment_link_create`, `booking_cancel`), gateway reconciliation (`razorpay`), reminders worker (`_scan_reminders_tenant` candidate slot/contact matching and booking comparison), and inbound worker (contact candidate matching for active conversation and booking queries). Added comprehensive regression suite `tests/test_generated_objectid_boundaries.py` (6 tests) and replica-set transaction test `test_generated_objectid_booking_transaction_lifecycle` in `tests/integration/test_booking_transactions.py`.
- **Implementation SHA:** `0baff57b019b840cf098199b0c03478985c49091` and `9b6d76ff416286e07daa9ec63f46c6d78fadf92c`.
- **Checks and workflow URL:** [CI Run 42595910578](https://github.com/DecoyINDIA/vaani/actions/runs/42595910578) (All jobs passed: quality, dashboard, booking-transactions replica set, recovery-drill, image build/smoke/scan/publish). Local gate: 124 passed (4 skipped), Ruff clean, mypy clean, evals 25/25 passed (Macro F1 1.0, 0 hallucinations). Published candidate: `ghcr.io/decoyindia/vaani@sha256:0222ea7c34526eec65b621620f6ac2317b18d9d7714860e85cdbbe88465e7104`.
- **Environment and sanitized evidence:** GitHub Actions Ubuntu-latest runners, MongoDB 7 replica set, Python 3.12, Node 22; synthetic test tenants and IDs only.
- **Remaining inputs / owner:** Restorable production backup access for read-only inventory execution, operator decisions on legacy timestamp provenance and collision handling (WP03; Backend implementer / Deployment operator).
- **Next package:** WP03 — Inventory and resumable migration (P2).
- **Remote main status:** Confirmed `9b6d76f` is on GitHub `origin/main`.

## Acceptance criteria by finding

### R01 Production authentication

- [ ] API and worker refuse production startup with default/missing/short secrets; tests also prove complete valid configuration starts.
- [ ] Tokens require expiry, subject, tenant, and correct purpose; invalid, expired, revoked, unknown-user, removed-membership, and cross-tenant requests are denied.
- [ ] Owner/staff permissions are explicit for every exposed endpoint; settings and billing changes require the appropriate role.
- [ ] Login issuance and token exchange have bounded attempts and replay protection. Record the secret rotation procedure and invalidate prior sessions when required.

### R02 Exotel ingress authorization

- [ ] Both call and missed-call routes reject unauthenticated or invalid provider requests before database writes or sends.
- [ ] An arbitrary caller cannot obtain a usable stream token by submitting a known clinic number.
- [ ] Stream grants reject expiration, replay, changed tenant, changed call ID, and changed caller metadata; account/call identity is verified through the supported integration.
- [ ] Tests cover positive provider-format requests and negative cases; staging proves the real provider can connect through the deployed proxy/TLS setup.

### R03 Identifier normalization

- [ ] Use real generated ObjectIds in API integration tests, not only string fixtures. Lists, detail reads, takeover, return, create, cancel, and move all succeed on those records.
- [ ] Serialize nested IDs; invalid IDs return a controlled client error, missing records return not found, and cross-tenant IDs never match.
- [ ] Booking creation returns a nonempty persisted ID; every stored reference resolves to the expected entity.
- [ ] Migration dry run reports orphan references and ambiguous IDs. The applied migration is resumable and preserves tenant boundaries.

### R04 Customer booking journey

- [ ] Parse text and supported WhatsApp button/list replies into normalized events; process every message in a webhook batch.
- [ ] Persist selected practitioner, service, date, slot, and confirmation state across turns. Echo the clinic-local date/time before executing a mutation.
- [ ] Book, status, cancel, and reschedule use the authenticated sender's contact; supplying another patient's booking ID is rejected.
- [ ] End-to-end tests assert database state and outbound confirmations for first booking, unavailable slot, repeated confirmation, cancellation, and rescheduling.
- [ ] Patient-facing success messages are generated only from committed operation results. Provider/LLM failures produce a real recovery or handoff path.

### R05 Staff handoff

- [ ] Explicit human requests and the documented safety/low-confidence triggers enter `human` state exactly once and create a usable escalation.
- [ ] Subsequent inbound messages remain in that thread, appear to staff, and produce no bot reply; queued replies cannot bypass takeover.
- [ ] Notify the configured staff recipient within the documented 30-second target in staging, deduplicate alerts, and expose failed notification delivery.
- [ ] Staff can reply, resolve, and return the conversation. Return requires a summary, restores `bot`, and supplies that summary to the next agent turn.
- [ ] Exercise the documented in-hours SLA/owner escalation path and out-of-hours behavior with an injected clock.

### R06 Provider-compatible voice

- [ ] Implement connected/start/media/dtmf/stop handling using official envelopes; reject malformed messages without corrupting session state.
- [ ] Decode the negotiated audio format, buffer utterances, invoke the configured STT, and send synthesized audio in the provider's required media envelope.
- [ ] Use currently supported STT/TTS model and speaker combinations. Decode Sarvam's actual response, validate nonempty audio, and fail visibly on bad provider responses.
- [ ] Demonstrate playback interruption while synthesis/playback is active; a boolean flag in a finished turn is insufficient evidence.
- [ ] Prove cleanup after stop/disconnect, low-confidence recovery, and real audio output using a sandbox call in each enabled language. Measure the existing PRD latency targets rather than simulated timings.

### R07 Voice caller isolation

- [ ] Bind caller identity to verified provider metadata; reject mismatched query parameters. Use an isolated ephemeral contact when identity is unavailable.
- [ ] Two callers cannot share contact, transcript, active conversation, or consent. A verified returning caller can recover only their own authorized history.
- [ ] Consent notice/version and acceptance evidence are associated with the correct caller; rejected/pending consent cannot enter a flow requiring acceptance.

### R08 Durable message processing

- [ ] Kill the process after receipt, after queue notification, during graph work, after business commit, and before acknowledgment; accepted messages remain recoverable.
- [ ] Simulate Redis outage at startup and during processing. Recovery must not depend on Redis being available before MongoDB fallback scanning begins.
- [ ] Simulate MongoDB outage: do not return successful acceptance unless the complete event is durably recoverable. A bare deduplication placeholder is insufficient.
- [ ] Two workers and duplicate provider events create one logical booking/escalation/outbound intent. Leases can be reclaimed after crashes.
- [ ] Failed outbound sends remain retryable; retry exhaustion and unknown delivery are visible to operators. Reconciliation never silently drops work or blindly repeats ambiguous side effects.
- [ ] Redis rebuild from persisted work is tested; queue retention/trimming cannot delete unprocessed durable work.

### R09 Tenant outbound routing

- [ ] Each tenant maps to the correct approved sender ID and credential reference; logs and API responses do not expose credentials.
- [ ] A two-clinic integration test verifies the actual outbound URL/account for each tenant, including reminders, staff alerts, missed-call messages, and summaries.
- [ ] Enabled production channels fail configuration checks rather than returning mock success. Preserve the 24-hour freeform-window guard.

### R10 Payments

- [ ] Create links through Razorpay using validated amounts, currency, tenant account, patient, and booking references; persist the returned provider ID and URL.
- [ ] Verify signatures over the raw body and handle the documented `payment_link.paid` event; include official sanitized fixtures rather than locally invented event names.
- [ ] Replayed or out-of-order events do not duplicate charges, receipts, or booking transitions. Unknown/mismatched amount, currency, account, or reference produces an observable reconciliation error.
- [ ] Payment after cancellation cannot silently reactivate a booking or overwrite someone else's slot. Persist payment status separately and route exceptions for resolution.
- [ ] Complete sandbox link-create/payment/webhook/status-display flow; never charge a real customer as a test.

### R11 Owner dashboard and sessions

- [ ] Complete invited-owner/staff magic-link login, session renewal, logout, expired-link, and removed-membership flows.
- [ ] Provide the minimum working inbox/transcripts, escalation queue, staff reply and return, booking calendar/actions, and settings/KB screens needed for the promised release scope.
- [ ] Show pending, failed, and unknown deliveries clearly; prevent duplicate form submissions and preserve errors rather than displaying false success.
- [ ] Verify role and tenant enforcement server-side, including staff-send authorization. Paginate and sort growing lists so records remain reachable beyond existing silent caps.
- [ ] Build the dashboard in a Node stage, copy assets into the Python image, and test root/deep-link loading after login from that image.
- [ ] Browser tests cover the key flows on desktop and phone-sized layouts. Install/configure ESLint or deliberately replace the script with an actual maintained check.

### R12 Booking consistency

- [ ] APIs and tools call the same transition functions; reject unsupported statuses and invalid transitions.
- [ ] Cancellation frees only the slot still owned by that active booking. Repeating an old cancellation after rebooking does not reopen the slot.
- [ ] Rescheduling either commits the new booking/slot ownership and releases the old slot together, or preserves the old valid booking after failure.
- [ ] Test failure between each write and 500 concurrent claims using real MongoDB; prove zero double bookings and no orphan booked slots.
- [ ] Hold expiry and confirmation check the owning operation. A retry returns the original result rather than creating another booking.

### R13 Reminder delivery

- [ ] Derive template name, language, parameter order/count, and values from a single approved contract. Validate against the actual provider approval, not only Markdown placeholders.
- [ ] Mark delivered only after confirmed send; persist retryable failures and deduplicate concurrent jobs. Unknown delivery follows R08 reconciliation policy.
- [ ] Re-evaluate the latest booking time/status before dispatch; cancel stale reminders after cancellation or movement.
- [ ] Honor recorded messaging preferences and STOP/opt-out behavior. Verify 24-hour and 2-hour reminders and failed-send recovery using an injected clock and sandbox templates.

### R14 Grounded output

- [ ] Reject source IDs absent from the current tenant's retrieved facts, including fabricated tags and references copied from earlier turns.
- [ ] Render fees, addresses, slot times, and booking/payment outcomes from structured results where possible. A valid citation cannot authorize an altered numeric fact.
- [ ] Tests cover false price with a valid tag, invented source, missing facts, injected instructions in patient/KB text, and multilingual unsupported claims.
- [ ] Separate offline pipeline tests from real-model evaluation. Require the existing intent F1 threshold of at least 0.85 and zero observed unsupported claims on the versioned release set; this is a measured gate, not a universal zero-hallucination guarantee.

### R15 Erasure and retention

- [ ] Inventory patient references and free-text PII in contacts, messages, conversations, bookings, payments, escalations, waitlist, audit data, queued work, and any provider/media records.
- [ ] Provide a tenant-scoped dry-run report, then a resumable erasure action with identity/authority verification and documented retained-record exceptions.
- [ ] Pseudonymize audit content and revoke or suppress pending sends; deletion must not be undone by a queued event or restored backup.
- [ ] Prove idempotency, cross-tenant isolation, free-text removal, retained-record handling, and application after restore with synthetic patient data.
- [ ] Document the existing seven-day request SLA, operator steps, provider deletion obligations, retention settings, and evidence of completion without retaining erased PII in the evidence itself.

### R16 Private Redis

- [ ] Remove the production host-port mapping; use the Compose service address rather than container-local `localhost`.
- [ ] Confirm API/worker connectivity over the intended private network and blocked external access in staging.
- [ ] Document separate local-development access if needed. Verify API and worker health independently; an HTTP healthcheck on a non-HTTP worker is not valid worker readiness.

### R17 Clinic-local time

- [ ] Use UTC instants consistently and `zoneinfo` for clinic-local interpretation/display. Host timezone does not affect results.
- [ ] Fix date phrase precedence and boundaries, including day after tomorrow, Hindi/Odia numerals, midnight IST, year changes, and ambiguous dates needing confirmation.
- [ ] Cover reminder offsets, weekly summary attribution, holiday closures, and scheduler execution with an injected clock.
- [ ] Backfill legacy times only after determining their provenance; list ambiguous rows for explicit resolution. Do not blindly subtract 5 hours 30 minutes from every timestamp.

### R18 Availability and onboarding

- [ ] Extend the rolling slot horizon daily with an idempotent job and unique slot constraints; test execution beyond the initial 14 days.
- [ ] Respect practitioner changes and holidays without deleting booked appointments. Surface conflicts for staff instead of silently changing commitments.
- [ ] Either implement validated tenant configuration input for onboarding or replace the misleading YAML command with an explicit supported input format. Keep demo seeding separate and restricted to test/dev environments.
- [ ] Alert on failed expansion or insufficient future availability; use bounded work per tenant.

### R19 Billing correctness

- [ ] Map provider plan IDs to canonical product plans and handle activation, change, cancellation, and failures explicitly.
- [ ] Product owner resolves the existing pricing disagreement before implementation. Derive invoices and displayed prices from the same configuration; reject unknown plans instead of charging Starter by default.
- [ ] Connect actual usage events with stable event IDs and units; replay does not double-count. Distinguish audio duration from provider request latency.
- [ ] Use integer minor units or decimal arithmetic, stable unique invoice IDs, a durable issuance record, and a defined monthly schedule/delivery path.
- [ ] Reject missing real billing identity rather than substituting a sample GSTIN. Test period boundaries, overages, retries, plan changes, and invoice reconciliation against the approved billing rules.

### R20 Release verification

- [ ] Use `uv.lock` for Python CI/image installation and commit a dashboard lockfile for `npm ci`; test on Python 3.12, the actual runtime target.
- [ ] Add the regressions specified above, full tenant/role route probes, real datastore integration, provider contract fixtures, and frontend checks to required CI jobs.
- [ ] Distinguish fast offline tests from credentialed provider/model gates. Store sanitized results with model IDs, configuration, corpus version, commit, and image digest.
- [ ] Audit the locked image and frontend dependency tree, triage reachability, and fix reachable high/critical vulnerabilities before release. Record rationale for remaining advisories rather than copying development-environment counts into release approval.
- [ ] Build once, start API and worker from that image, exercise dashboard and webhook journeys, restore to staging, and promote only the verified digest.

## Data migration and rollback

Complete a read-only inventory before applying any migration: collection counts by tenant, `_id` and foreign-key types, orphan references, duplicate contacts/active conversations, legacy `open` states, placeholder/queued messages, slot ownership, timestamp provenance, and provider plan values. Store counts and redacted examples, not patient transcripts.

1. Verify a restorable backup and record its identifier. Pause ingress and workers during incompatible backfills; configure provider retry handling so events are not acknowledged and discarded during maintenance.
2. Apply additive fields and indexes first. Normalize references and conversation states, backfill timezone/slot ownership only where unambiguous, and report records requiring operator decisions.
3. Classify stranded placeholders and queued records. Recover from durable payloads where available; explicitly report unrecoverable historical payloads. A migration cannot reconstruct messages that were never persisted.
4. Validate counts, tenant boundaries, ownership constraints, and indexes. Re-run interrupted migrations to prove idempotency. Reconcile preexisting duplicate records before enabling uniqueness constraints.
5. Deploy the compatible image and replay pending work under leases. Verify no duplicate booking, payment transition, or outbound intent is created.

Keep a compatibility window where possible so reverting the image does not require reverting data. If schema compatibility is lost, pause writes and use the tested recovery path; never restore an old snapshot over new paid transactions without reconciling the intervening events. Erasure suppression records must be reapplied after restore. Redis rebuild must use persisted work, not assumptions about provider redelivery.

## Staging and release gates

All checkboxes below are **Pending** and require full release-scope evidence. The completed narrower CI milestones in the current-status section do not satisfy these composite staging gates.

- [ ] R01–R20 acceptance criteria pass for the enabled product scope, with no unresolved Critical or High defects.
- [ ] The exact release image starts API and worker with production-mode configuration, real MongoDB/Redis, and no implicit mock adapters.
- [ ] Two tenants complete independent WhatsApp booking, cancellation, rescheduling, reminders, human takeover, staff reply, and return; negative cross-tenant tests pass.
- [ ] Enabled voice completes authenticated real calls, correct caller isolation/consent, STT/TTS, interruption, handoff, and measured latency checks.
- [ ] Enabled payments complete the sandbox create/pay/webhook flow, billing plan mapping, usage and invoice checks, duplicate events, and cancellation/late-payment cases.
- [ ] Crash/outage tests leave every accepted event completed, recoverable, or visibly failed/unknown; no silent disappearance.
- [ ] Real-model evaluation meets the documented thresholds on the frozen multilingual corpus; mock scores are reported separately.
- [ ] Load/race tests meet the existing PRD targets, with 500 concurrent slot claims producing zero double bookings. Record queue age and provider error behavior under load.
- [ ] Alerts for queue age, dead letters, unknown delivery, provider failures, worker heartbeat, and schedule exhaustion reach the configured staging destination during a drill. Avoid PII in alert payloads.
- [ ] A timed restore meets the existing targets of RTO at most 15 minutes and RPO at most 1 hour; demonstrate Redis rebuild and reapplication of erasure records.
- [ ] Erasure, retention, approved templates, provider data settings, billing identity, and existing business/compliance gates have recorded evidence from their responsible owners.
- [ ] Deployment operator records image digest, migration/backup identifiers, rollback conditions, and the initial limited pilot tenant set. Expand only after the pilot's own gates pass.

An explicitly approved narrower release may disable voice or billing, but those routes, UI promises, jobs, and credential requirements must be consistently disabled and tested. Merely marking an unfinished feature optional does not close its findings. No reduced release scope has been approved by this plan.

## Verification commands

Current baseline commands, run in an isolated environment with synthetic data:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe evals/run_evals.py --ci
uv build --wheel
```

Run `npm run build` and `npm run lint` from `dashboard`; both are required local and CI gates. The current eval command calls the demo seeder; do not point it at a production database. Reproduction scripts from the review must become isolated committed regressions rather than relying on chat history.

Run the real booking transaction/race suite against an isolated MongoDB replica set:

```powershell
$env:USE_MOCK_ADAPTERS="false"
$env:VAANI_INTEGRATION_MONGODB_URI="<synthetic-test-replica-set-uri>"
.venv\Scripts\python.exe -m pytest -q tests/integration/test_booking_transactions.py
```

The suite deletes only tenants prefixed `integration-` from `slots` and `bookings`. It is skipped when the URI is absent; a skip is not release evidence.

The committed `.github/workflows/ci.yml` is the current runnable authority for required real-datastore races, image smoke/crash checks, dependency scans and synthetic recovery (`ops/recovery_drill.py`). `.github/workflows/credentialed-retrieval.yml` and `evals/run_retrieval_eval.py` define the separate credentialed retrieval gate. Completed runs are recorded above and in the ledger. WP04–WP11 must document the exact remaining provider, browser, real-model, staging-load and timed-recovery commands/configuration as those environments become available; these are not yet a complete passing release gate.

## Completion ledger

Update each row as work proceeds. Valid statuses are Open, In progress, Blocked, Verified, and Deferred by explicit scope decision. A Verified row needs a commit/PR, test evidence, and reviewer. A scope deferral must name the disabled feature and decision; it is not a fix.

| Finding | Package | Status | Implementer | Commit or PR | Evidence and reviewer |
| --- | --- | --- | --- | --- | --- |
| R01 | P1 | In progress | Codex | `c136516` | Local secret, membership, purpose, role, 15-minute one-use invitation, replay/expiry, persisted per-subject issuance and per-client exchange limits, access-session, rotating refresh, removed-membership, logout revocation, and complete anonymous/staff/owner/cross-tenant owner-route probes pass; permissions and fail-closed secret rotation/session invalidation are documented. LLM calls now require either a real OpenRouter key or an explicitly selected mock mode, propagate missing-key/provider failures instead of silently returning rule-based output, omit prompts and provider response bodies from adapter logs, and reject both all-adapter and LLM-only mock modes at staging/production startup. Staging proof and reviewer remain |
| R02 | P1 | In progress | Codex | Included in baseline `e3c1205` | Callback identity is checked through Exotel's Basic-authenticated Call Details API before side effects; stream grants are 60-second, one-use, and bound to tenant/call/caller with negative replay and mutation regressions; real Exotel/proxy/TLS proof remains |
| R03 | P2 | In progress | Codex | `0baff57` and `9b6d76f` | Recursive ObjectId serialization, external string/ObjectId matching for conversation takeover/return/responder/escalation, returned booking-ID regressions, and a read-only redacted inventory for ID types, ambiguous values, reference types, orphans, duplicate contacts/conversations, legacy states, queued placeholders, and slot ownership pass locally. Commits `0baff57` and `9b6d76f` hardened all booking, slot, contact, payment, reminder, and inbound generated-ObjectId boundaries with `TenantScoped.resolve_id()`, ambiguous collision rejection (409), cross-tenant denial, and candidate resolution in background workers. Required CI run `42595910578` passed 124 unit/boundary tests and replica-set transaction tests for generated-ObjectId booking/move/cancel lifecycle. Read-only inventory execution on a production backup and resumable backfill remain in WP03 |
| R04 | P4 | In progress | Codex | `e3c1205` | Multi-message durability plus Meta text/list/button normalization and a persisted practitioner/service/date/slot flow execute committed create, repeated confirm, status, patient-scoped cancel, and atomic reschedule journeys locally; a slot taken between selection and confirmation returns a fresh picker without false success, and confirmation-send retries reuse the original delivery/transcript operation key. Classifier and responder provider failures now carry a fixed non-sensitive `llm_unavailable` marker through the existing handoff node, create a durable escalation, set the conversation to `human`, and return the real handoff acknowledgement instead of a false synthetic answer or an unfulfilled notification promise. Required run `42588684213` passed both failure-stage regressions and the exact-image graph/crash path; provider sandbox proof remains |
| R05 | P4 | In progress | Codex | `e3c1205` | Explicit human request, one open escalation, stable staff alert, visible missing/failed/unknown delivery, generated-ID takeover, replay-safe staff reply/transcript, required resolution summary, return-to-bot, clinic-local in-hours 10-minute owner escalation, and localized out-of-hours queue/next-opening behavior pass with an injected clock. Classifier and responder outages now use that same durable handoff path and expose the fixed failure reason without persisting provider exception text. Required release-image run `42588684213` retained the real Redis/Mongo worker and crash matrix after this routing change; real 30-second/10-minute staging delivery proof remains |
| R06 | P6 | In progress | Codex | Included in baseline `e3c1205` | Official connected/start/media/dtmf/mark/stop envelopes, sequence and call metadata validation, base64 linear16 framing, negotiated-format audio output, silence utterance buffering, provider clear on barge-in, current Saaras v4/Bulbul v3 contracts, and malformed-input checks pass locally; real sandbox audio/latency and supported production voice selection remain |
| R07 | P6 | In progress | Codex | Included in baseline `e3c1205` | Verified caller metadata is bound into one-use stream grants and voice contacts; missing identity uses a per-call ephemeral key; caller consent/contact isolation, returning-caller recovery, and pending-consent blocking pass locally; real-provider two-caller proof remains |
| R08 | P3 | In progress | Codex | `49e67f5` | Durable-before-ack, leases, persisted outbound intents, ambiguous-send protection, delivery reconciliation, and idempotent flow transcript/audit recording pass; queue payload remains in Mongo until processing completes, generic reply transcripts and keyed inbound audits are replay-safe, and local tests recover an expired lease without Redis. Retry exhaustion marks the durable Mongo work item `failed` before acknowledging Redis, prevents Mongo fallback from retrying it forever, removes the raw terminal exception string, and exposes only paginated PII-free failure metadata to tenant staff. Every shared WhatsApp send now keys its audit to the same operation identity as the durable outbound intent, so a provider replay yields one intent and one success audit; ambiguous delivery emits no false success audit, and the missed-call bridge records its legacy success event only after confirmed send. Required run `42558339294` passed these regressions and retained the full exact-image crash/recovery matrix; staging alert-destination proof and independent review remain |
| R09 | P1 and P3 | In progress | Codex | Included in baseline `e3c1205` | Every non-mock send now resolves a tenant-owned sender ID and environment credential reference before persisting an intent; missing mappings fail closed, no secret appears in errors, and two-clinic URL/account regressions cover freeform/template paths shared by reminders, alerts, bridges, and summaries; real two-clinic provider proof remains |
| R10 | P6 | In progress | Codex | Included in baseline `e3c1205` | Official-shaped link creation, minor-unit validation, raw-body signatures, payment_link.paid fixture, replay/mismatch/late-payment reconciliation pass locally; real sandbox flow remains |
| R11 | P5 | In progress | Codex | `989867a` | Invited-user login, one-use exchange, access/rotating-refresh sessions, logout, removed membership, inbox/transcript paging, takeover, replay-safe staff reply, return summary, appointments, escalations, PII-free paginated delivery and inbound-processing issues, knowledge editing, and owner settings are connected; growing lists have deterministic server sort and reachable offset pages, mutations prevent repeat submission, and TypeScript/build pass. Knowledge writes now require and persist the configured embedding before replacing an entry, return 503 without destroying the prior record when embedding fails, and never expose vectors through the owner API; dry-run-first resumable re-embedding is documented. The responsive login shell was visually checked at 1440×900 and 390×844, while an authenticated browser journey exercised magic login, inbox reply/return/takeover, appointments, resolved escalation, knowledge write, owner settings write, and logout with no console warnings/errors; exact-image run `42531156130` authenticated as staff and retrieved synthetic unknown-delivery and exhausted-processing records without recipient, operation-key, inbound payload, or transcript fields. A real staging browser write/read check against configured Atlas indexes and independent review remain |
| R12 | P4 | In progress | Codex | `f5be5a0` | Shared guarded transitions and local ownership/idempotency regressions pass; required GitHub Actions run `42390315130` started MongoDB 7 as a replica set and passed the rollback plus 500-concurrent-claim suite in 1.49 seconds with one booking and no orphaned slot; production-topology load evidence and independent review remain |
| R13 | P3 | In progress | Codex | `120d0c3` | Reminder claims, stale ownership checks, opt-out suppression, failure/unknown visibility, stable send keys, tenant/contact language selection, and exact approved 24h/2h parameter names/order pass. Staff alert, weekly summary, and missed-call parameter contracts are enforced, with the bridge sending clinic name rather than caller phone into `{{1}}`. Weekly summaries now select each tenant in its own Sunday 23:00 hour, use one provider/audit operation per clinic-local ISO week, retry durable failed sends, preserve unknown results, record a keyed PII-free alert instead of a false send when the owner recipient is missing, and continue other tenants after one tenant fails. Reminder scans likewise never reacquire an ambiguous `unknown` send, normalize an aware injected clock to naive UTC before comparing stored instants, and isolate each tenant so an invalid timezone records one daily keyed PII-free alert without starving later tenants. Required run `42559133558` passed these regressions; actual Meta approval export and sandbox delivery proof remain |
| R14 | P4 | In progress | Codex | `e3c1205` | Invented-source and altered-number regressions pass locally. Tenant-filtered Atlas `$search` and `$vectorSearch` inputs are combined with MongoDB 8+ `$rankFusion`, followed by a defensive tenant match; if embeddings or Atlas search fail, retrieval permits only an exact tenant-scoped structured key and free-text missing facts route directly to human handoff. Contract tests cover both ranked tenant filters, cross-tenant fallback denial, provider request shape, a 50-query multilingual retrieval corpus, and the no-result handoff path. Missing credentials and classifier/responder provider failures now traverse the graph's durable staff-handoff path rather than substituting synthetic rule-based replies or returning a false notification promise. A manual credentialed workflow can seed an isolated `eval` database, run real OpenRouter embeddings plus Atlas retrieval, require top-3 accuracy of at least 90%, clean its synthetic tenant, and retain only a summary artifact, but it has not been run; provisioned Atlas indexes, approved embedding model/secrets, the measured retrieval threshold, and the release-set real-model gate remain |
| R15 | P7 | In progress | Codex | `5eb7e7f` | Tenant-scoped dry-run/apply, idempotency, cross-tenant isolation, PII scrubbing, queued-send suppression, and operator runbook pass locally; required run `42478330865` restored a synthetic MongoDB backup, reapplied a hashed erasure marker, and proved it still blocked delivery in artifact `13616731369`; retention approval, provider deletion, external erasure-ledger operation, and a timed staging restore remain |
| R16 | P1 | In progress | Codex | Included in baseline `e3c1205` | Redis host publication removed and worker heartbeat healthcheck added; staging network proof remains |
| R17 | P2 | In progress | Codex | `120d0c3` | Tenant timezone, UTC slot storage, local slot display/reminder/summary attribution, phrase precedence, Indic digit, and boundary regressions pass. The scheduler now scans weekly summaries independently of host-local weekday/hour and the worker selects the correct Sunday 23:00 window per tenant timezone. Reminder scans normalize aware UTC clocks before comparing the existing naive-UTC stored instants, and an invalid tenant timezone cannot stop later tenant scans. The read-only migration inventory classifies naive, aware, and non-datetime timestamp fields without guessing provenance; production-backup inventory, operator decisions, and backfill remain |
| R18 | P2 | In progress | Codex | Included in baseline `e3c1205` | Persistent clinic-day expansion, unique slots, injected-clock horizon/idempotency, bounded tenant scans, durable PII-free failure/exhaustion alerts, retained failed job state, and continuation after one tenant fails pass locally; validated JSON onboarding is dry-run by default, stores only credential references, rejects cross-tenant practitioner collisions, and reruns without deleting bookings; demo seeding is explicitly `--demo`-only and restricted to dev with mocks; alert-destination delivery and staging operation remain |
| R19 | P6 | In progress | Codex | `4464141` | Canonical plan/provider mapping, explicit lifecycle states, replay-safe unit-bearing events, billable Meta delivery and verified Exotel conversation-duration producers, tenant-local periods, integer-paise durable invoice snapshots, monthly issuance, and boundary/overage/retry/plan-change regressions pass. Voice metering uses provider `ConversationDuration`/`EndTime`, rejects callback mismatches, and never bills request latency. Monthly issuance now isolates tenants: an invalid timezone, plan, or billing identity cannot prevent later tenants from being invoiced, and each failed tenant/period produces one keyed PII-free operational alert while subsequent scans retry. Required run `42557166514` passed the regression and all downstream gates; GST/SAC approval, invoice rendering/delivery, configured alert delivery, and real provider reconciliation proof remain |
| R20 | P0 and P8 | In progress | Codex | `e3c1205` | Lock-based Python/Node CI, wheel/frontend builds, complete owner-route probes, a clean tenant-isolation source gate, and required complete Python/frontend audits with 0 known vulnerabilities pass; mock evals pass 25/25 and remain explicitly labeled non-model evidence. Run `42560108327` deliberately exposed that the exact-image test had depended on an undeclared missing-key LLM fallback; its image smoke failed after that fallback was removed, and no candidate was published. Replacement run `42587461110` explicitly selected only the offline LLM while retaining real MongoDB, Redis, provider-ambiguity, and crash behavior. Current required run `42588684213` added both classifier- and responder-outage handoff regressions, passed 118 tests with 3 environment skips and every quality, dashboard, MongoDB replica-set transaction/race, backup/restore, exact-image API/dashboard/webhook/worker/crash-recovery, and fixed High/Critical Trivy gate. It retained sanitized mock-eval artifact `13660646000` (`sha256:0a383e0514b8ec51500d50bf4c318414f35b6be51fbb5f03421c9901b738284b`) and synthetic-recovery artifact `13659489451` (`sha256:5eb671950478f4766119b85f3cc8e0722fc133074b930dad36818ecfd40c5c2a`), built current-HEAD image `sha256:23bd0557433216aaa78dd207e887ca1d44200fa95a0035792d03671830e79558`, and published the verified candidate as `ghcr.io/decoyindia/vaani@sha256:3fb32b75b34965c74f0f36224f08f5d3ff8e78a9f48e72f5f417f6b7fdaa7897` under unique tag `candidate-e3c1205bb64d96f5fc3ebd39a3608b43039c72fa-42588684213-1`. The credentialed retrieval workflow is registered but cannot run because its Actions secrets and model/index variables are not configured; real provider/model, timed staging RTO/RPO, broader load, release-tag promotion/deployment, staging, and independent-review gates remain |

For every closure, record the original failure scenario, regression test, fix, datastore/provider environment, exact result, residual limitations, and reviewer. Keep a dated changelog below; do not rewrite the original review evidence to imply the defect never existed.

## Changelog

| Date | Change | Release impact |
| --- | --- | --- |
| 9 November 2026 | WP02 completed at `0baff57` and `9b6d76f`, CI run `42595910578`, candidate digest `sha256:0222ea7c34526eec65b621620f6ac2317b18d9d7714860e85cdbbe88465e7104`; resolved generated ObjectId vs legacy string boundaries across models, booking engine, owner APIs, payment links, Razorpay gateway, reminders and inbound workers with ambiguous collision rejection and cross-tenant isolation | R03 ID boundaries hardened and verified in CI with replica-set transactions; unblocks WP03 migration |
| 9 November 2026 | WP01 baseline confirmed at `4567c5e`, CI run `42591587840`, verified candidate digest `sha256:48cb55552b65bb10ad3e55a6976f51163c28691a9594318f2b9ae89767da9056`; established explicit input register with 17 tracked items, owners and next actions | Baseline confirmed; WP02 unblocked, external provider/staging/decision inputs tracked as Pending |
| 9 November 2026 | Reconciled status at `6fcd7e8`, rechecked successful GitHub run `42588684213`, separated Complete implementation/CI milestones from Pending final finding closures, and added WP01–WP12 with steps, dependencies, exit evidence and mandatory per-package commit/push to main | Documentation handoff only; all final finding closures and production release remain pending |
| 6 November 2026 | Recorded review evidence, all 20 findings, implementation packages, acceptance criteria, migrations, and release gates | Planning only; release remains blocked |
| 7 November 2026 | Recorded dirty-checkout baseline; began fail-closed config/auth, guarded booking transitions, durable inbound/outbound delivery, reminder recovery, grounding/date regressions, private Redis, lock-based CI, and dashboard image build | Local remediation in progress; no finding verified and release remains blocked |
| 7 November 2026 | Replaced stale billing constants and implicit provider plans with a canonical catalog, replay-safe usage events, durable paise invoices, explicit subscription lifecycle handling, and monthly issuance | R19 implementation in progress; real invoice delivery, voice metering, provider reconciliation, approvals, and review remain release blockers |
| 7 November 2026 | Replaced caller-supplied Exotel stream authorization with provider API verification and short-lived one-use grants bound to tenant, call, and caller | R02/R07 implementation in progress; real provider/proxy call and full caller-isolation evidence remain release blockers |
| 7 November 2026 | Replaced the test-only binary voice socket with Exotel AgentStream envelopes and linear16 framing; updated Sarvam STT/TTS to current documented models and response shapes; made consent explicit | R06/R07 implementation in progress; sandbox calls, production voice selection, and measured real latency remain release blockers |
| 7 November 2026 | Added a persisted WhatsApp interactive booking flow and completed explicit handoff notification/return behavior with generated-ID-safe transitions | R03/R04/R05 implementation advanced; sandbox journeys, SLA drills, migrations, and review remain release blockers |
| 7 November 2026 | Replaced the global WhatsApp sender/token path with tenant sender IDs and environment credential references, with two-tenant routing regressions | R09 implementation advanced; real two-clinic provider proof and onboarding validation remain release blockers |
| 7 November 2026 | Added one-use invitation exchange, rotating/revocable sessions, logout and membership rechecks; connected the owner dashboard's inbox, staff handoff/reply, appointments, escalations and settings; visually checked desktop/mobile login breakpoints | R01/R05/R11 implementation advanced; authenticated browser/container journeys, issuance throttling, staging proof, review, and other release gates remain blockers |
| 7 November 2026 | Re-ran the complete local gate: Ruff and mypy passed, 76 tests passed with 3 real-integration skips, dashboard lint/build passed, mock evaluation passed 25/25 with macro F1 1.0 and zero observed unsupported claims, and `git diff --check` passed | Local evidence improved only; Docker, real Mongo/provider/model, migration, recovery, load, security, commit/PR, and independent-review gates remain unresolved |
| 7 November 2026 | Made rolling schedule expansion retain per-tenant failures, continue other tenants, and emit PII-free operational alerts when expansion fails or the end of the booking horizon has no open slots | R18 implementation advanced; production onboarding and delivery of alerts to a configured staging destination remain release blockers |
| 7 November 2026 | Added a read-only migration inventory that emits counts and hashed samples for ID/reference types, collisions, orphans, duplicate contacts/active conversations, legacy states, queued placeholders, slot ownership, timestamp provenance, and plan values | R03/R17 migration preparation advanced; it must still run against a restorable production backup and feed an approved, resumable backfill |
| 7 November 2026 | Bound 24-hour and 2-hour reminder sends to the documented positional variable contracts and supported languages, deriving practitioner, clinic-local date/time, landmark and contact locale from tenant data | R13 implementation advanced; the artifact still requires comparison with the actual Meta approval and sandbox delivery evidence |
| 7 November 2026 | Added an explicit staff/owner permission matrix and route probes for every owner business endpoint, including anonymous denial and cross-tenant non-disclosure/non-mutation | R01/R20 local authorization evidence advanced; staging and independent review remain required |
| 7 November 2026 | Added deterministic server-side paging/sorting and dashboard “load older” paths for conversations, messages, bookings, escalations, knowledge and audit records; connected knowledge editing and guarded repeated staff/settings/booking submissions | R11 implementation advanced; authenticated browser journeys and release-image deep-link checks remain blockers |
| 7 November 2026 | Added persisted invitation/exchange attempt limits and documented a fail-closed JWT secret rotation that revokes all sessions before replacing the shared API/worker secret | R01 local acceptance advanced; staging execution and independent review remain blockers |
| 7 November 2026 | Made booking confirmation delivery replay-safe after a committed mutation and returned patients to a remaining-slot picker when their selected slot was taken, with operation-keyed interactive/text transcript records | R04/R08 local recovery evidence advanced; real provider and crash-matrix proof remain blockers |
| 7 November 2026 | Added an Exotel terminal-status endpoint that re-verifies Call Details with leg details, meters provider conversation seconds once under the call SID, assigns the period from provider end time, and rejects callback/API duration mismatches | R19 voice metering producer implemented locally; real callback/reconciliation and invoice delivery evidence remain blockers |
| 7 November 2026 | Added clinic-local handoff SLA state, a replay-safe owner alert after an in-hours 10-minute breach, and localized out-of-hours queue messaging with the next configured opening | R05 local SLA behavior implemented; measured provider delivery timing still requires staging |
| 7 November 2026 | Expanded the final local gate to 91 passing tests (3 environment skips), Ruff/mypy, wheel and dashboard builds, 25/25 mock evals, zero production frontend audit findings, and a clean whitespace check | Local evidence only; Docker's Linux engine remains unavailable and the real Mongo replica URI/provider/model/staging/reviewer inputs remain absent |
| 7 November 2026 | Replaced the unfixed `python-jose`/`ecdsa` JWT dependency chain with PyJWT, upgraded Certifi, dnspython, LangGraph SDK, PyMongo and urllib3 to fixed versions, and reran the Python audit with no known vulnerabilities | R20 locked-environment security evidence improved; release-image scanning and independent triage still require the Docker/staging path |
| 7 November 2026 | Enforced positional contracts for staff alerts, weekly summaries and missed-call bridges, and corrected the bridge placeholder from caller phone to clinic name | Provider-template drift reduced locally; actual Meta approval exports and sandbox sends remain required |
| 7 November 2026 | Added validated JSON tenant onboarding with a dry-run default, explicit apply confirmation, credential references, cross-tenant collision rejection, idempotent slot expansion, and no-delete booking preservation | R18 production input is implemented locally; configured alert delivery and a staging onboarding rehearsal remain release blockers |
| 7 November 2026 | Made the MongoDB replica-set rollback and 500-concurrent-claim suite a required GitHub Actions gate; run `42390315130` passed both tests and the downstream image smoke/scan | R12 real transaction evidence advanced and R20 now blocks the image build on it; production-topology load and review remain |
| 7 November 2026 | Added a summary-only mock-eval evidence artifact containing commit/model IDs, adapter mode, corpus hash/count, thresholds and per-language outcomes; required run `42390841126` uploaded artifact `13581243234` and passed all downstream gates | R20 reproducibility improved without retaining utterances/responses or overstating mock results as model evidence; credentialed model evaluation remains external |
| 8 November 2026 | Added a required synthetic backup/recovery drill using real `mongodump`/`mongorestore`, fresh Redis, durable Mongo work recovery, Redis coordination rebuild, and restored erasure suppression; run `42478330865` retained artifact `13616731369` | R08/R15/R20 recovery mechanics now have reproducible evidence; Atlas backup/RPO and timed staging RTO remain release gates |
| 8 November 2026 | Responded to Trivy's newly published fixed zlib High findings by applying Debian security updates in the image, and upgraded the Vite build chain after the complete frontend audit exposed a separate High advisory | Replacement run `42478330865` passed complete frontend audit, image smoke, and the fixed High/Critical Trivy gate |
| 8 November 2026 | Extended the exact-image smoke gate with a Meta-shaped webhook through API, Redis, worker and MongoDB, requiring durable acceptance, duplicate rejection, human-owned bot silence, and persisted audit/transcript evidence | Required run `42478893833` passed the new journey and rebuilt/scanned image `sha256:46aaf3cb4af5da7248a23eee9c8ffda498e5d466c3aeaa726e7449db7aa95eef`; external-provider and crash-kill evidence remain |
| 8 November 2026 | Made the complete dashboard dependency audit a required job and published the exact post-smoke, post-scan image to GHCR under a unique candidate tag and immutable digest | Required run `42492847992` passed every job and published `ghcr.io/decoyindia/vaani@sha256:993ee253cc744d72107003d4fb5fe4875a8ccd54b86570eb4551890b5b796410`; no release tag was promoted and no environment was deployed |
| 9 November 2026 | Kept the durable inbound payload until processing completion, made generic reply transcripts and keyed inbound audits replay-safe, added exact-image kills at all six inbound lifecycle checkpoints, reconciled process-interrupted provider sends from stale `sending` to `unknown` without retry, and exposed paginated PII-free delivery issues to staff | Required run `42530142702` passed 101 tests and every downstream gate, recovered all six accepted inbound events exactly once, proved a synthetic HTTP provider received one request before the sender was killed, blocked the ambiguous replay with the provider count still one, authenticated the staff delivery-exception API without leaking recipient/operation-key data, and published `ghcr.io/decoyindia/vaani@sha256:208ec2c61bba7d768d7df980674c182e42a525321274e1f2a7846d0910e4b5b0`; staging alert delivery and independent review still block R08 verification |
| 9 November 2026 | Made inbound retry exhaustion durable before Redis acknowledgment, removed raw terminal exception text, prevented the Mongo fallback from reprocessing exhausted work, and added a paginated tenant-scoped Processing issues view containing no inbound payload or transcript | Required run `42531156130` passed 103 tests and all downstream gates, authenticated the new PII-free processing API from exact image `sha256:135333c81dc7c1bb4b0f4b87824903cd56d6eac1ce605fc27f8b138d21d8b141`, and published `ghcr.io/decoyindia/vaani@sha256:ed7e26802ba75e35e06724f6b92c85a2ce5bcc7b538db14da52c91ed2c3ba623`; configured staging alert delivery and independent review remain blockers |
| 9 November 2026 | Replaced the KB embedding/retrieval stubs and unsorted regex lookup with embedding-on-write, tenant-filtered Atlas text/vector rank fusion, exact-key-only degradation, missing-fact handoff, a resumable backfill, a versioned 50-query multilingual retrieval set, and a summary-only credentialed retrieval workflow | Required run `42555626029` passed 111 tests plus all downstream image gates and published `ghcr.io/decoyindia/vaani@sha256:f72a82699342aa87507c59e9e5c39ffb320fd3e5d3bb93d9fda888c6b4817c3b`; the credentialed Atlas/OpenRouter workflow was not launched, so index provisioning, approved model/secrets, real top-3 measurement, staging proof, and independent review remain blockers |
| 9 November 2026 | Isolated monthly invoice issuance per tenant so invalid timezone, plan, or billing identity data cannot starve later tenants; added one replay-safe PII-free operational alert per failed tenant/period and documented automatic retry | Required run `42557166514` passed 112 tests and all downstream image gates, built image `sha256:1886ba03e773578071bcc0bc5d06575fa43f1716f4ed9b4ae80b239fd5f5016f`, and published `ghcr.io/decoyindia/vaani@sha256:089963fc5d62fd08bbed2016eaa101ab97706772dd2d70a2957ab9d02a70d495`; GST/SAC approval, invoice rendering/delivery, staging alert delivery, provider reconciliation, and independent review remain blockers |
| 9 November 2026 | Keyed all shared WhatsApp success audits to their durable outbound operation, removed pre-send weekly/missed-call success records, moved weekly eligibility from the host clock into each tenant's Sunday 23:00 window, and isolated missing-recipient or per-tenant failures | Required run `42558339294` passed 114 tests and all downstream image gates, built image `sha256:e33884806572840911c5090a8d073a4c40e1f0db70cb985f4de06242468d221c`, and published `ghcr.io/decoyindia/vaani@sha256:dbcc0331ffc71366dd3dd965ae0e78db8cd09a11588a58f0c89d31f3b5749985`; real template approval/export, sandbox sends, configured alert delivery, staging proof, and independent review remain blockers |
| 9 November 2026 | Prevented ambiguous reminder sends from being reclaimed, normalized aware injected clocks before stored UTC comparisons, and isolated reminder scans per tenant with one daily keyed PII-free failure alert | Required run `42559133558` passed 115 tests and all downstream image gates, built image `sha256:277999a956ae385f89787f2dd8395389484884d6490b853cd5bdb60380494d5e`, and published `ghcr.io/decoyindia/vaani@sha256:7357f7cb90b3189c7eacc0bb1db5bb213292b6778e6a2a0223d2e9da253b81e8`; actual Meta approval, sandbox delivery, production-backup timestamp migration, configured staging alert delivery, and independent review remain blockers |
| 9 November 2026 | Removed silent rule-based LLM substitution for missing credentials and provider failures, redacted prompts/provider bodies from adapter logs, and added a separate explicit dev-only LLM mock selector so exact-image tests can retain real datastore and delivery behavior | Initial run `42560108327` failed the image smoke because it revealed the gate's undeclared fallback dependency; replacement run `42587461110` passed 116 tests and every downstream gate, built image `sha256:7da42f16c1285aea7ad178930204547236271828a9512e3b3e0212d6f2165276`, and published `ghcr.io/decoyindia/vaani@sha256:8d909d29d1820c126a1b556c1af94a138c0801c766864809bbb57aabfcb0fb6a`; credentialed real-model evaluation, staging failure-path proof, and independent review remain blockers |
| 9 November 2026 | Routed both classifier and responder provider failures through the existing durable handoff node with a fixed PII-free error marker, a real escalation, human ownership, and the localized handoff acknowledgement | Required run `42588684213` passed 118 tests and every downstream gate, built image `sha256:23bd0557433216aaa78dd207e887ca1d44200fa95a0035792d03671830e79558`, and published `ghcr.io/decoyindia/vaani@sha256:3fb32b75b34965c74f0f36224f08f5d3ff8e78a9f48e72f5f417f6b7fdaa7897`; credentialed real-model failure injection, measured staging alert delivery, and independent review remain blockers |
| 7 November 2026 | Moved schedule job-state writes behind the tenant-scoped model boundary and reran the final local gate with 93 passing tests, 3 environment skips, clean Ruff/mypy/source-isolation checks, wheel and dashboard builds, 25/25 mock evals, and zero audited Python or production-frontend vulnerabilities | Reproducible local evidence is green; release remains blocked on the explicitly external Docker, replica-set, provider/model, backup/recovery, approval, staging and independent-review gates |
| 7 November 2026 | Retried the installed Docker Desktop 4.77.0 engine and captured its backend failure on the stale `AppData/Local/Docker/run/dockerInference` reparse point; the service is inaccessible from the current session and the exact runtime artifact could not be removed under host policy | Release-image build/scan requires an administrator to repair or restart Docker Desktop; no images, volumes, or project files were removed |
| 7 November 2026 | Fixed the first Linux CI failure by preventing after-hours handoff messaging from replacing mandatory static medical/complaint/abuse safety responses; added a direct regression and reran the 25-case eval successfully after clinic hours | R14 safety behavior is now time-independent; replacement GitHub Actions run `42375542461` passed quality, dashboard, wheel, eval, and Linux image-build jobs |
| 7 November 2026 | Upgraded CI actions to Node-24-compatible releases and made the release-image job start the API and worker from one tag against MongoDB/Redis, probe API/dashboard/worker readiness, record the image identity, and scan fixed High/Critical OS/library vulnerabilities | GitHub Actions run `42375897838` passed all jobs with zero Trivy findings; registry publication/promotion and credentialed staging evidence remain |
| 7 November 2026 | Pinned CI to Ubuntu 24.04 and moved uv downloads to a BuildKit cache mount so dependency archives are not retained in the release image | GitHub Actions run `42385226655` passed quality, dashboard, API/worker smoke, and Trivy gates for image `sha256:9146306c8b21d65a261d19e191eab7f46f48b7493ec388f41bd012db566bf20f`; promotion and staging remain |
| 7 November 2026 | Ran the authenticated dashboard in a real browser through magic login, staff reply, return, takeover, appointments, escalations, knowledge, owner settings, and logout; reconciled the selected conversation after reload so ownership and new transcript messages update immediately | R11 authenticated local browser evidence now passes without console warnings/errors; GitHub Actions run `42385856049` rebuilt, smoke-tested and scanned the current-HEAD image successfully; staging and independent review remain |
