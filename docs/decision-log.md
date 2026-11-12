# Decision log

## 12 November 2026 - Waves 1-2 execution authority

- Scope: implement every written Wave 1 packet, pass INT-1, then implement every written Wave 2 packet and attempt INT-2. Unwritten Wave 3-4 work is out of scope.
- Integration: work directly on `main`, one packet per commit, after the concurrent remediation task leaves a clean working tree. No task branches or worktrees.
- Observability: adding `sentry-sdk>=2` is approved. Use Sentry's free Developer plan, disable tracing, set `send_default_pii=False`, and apply the packet's scrubber. A missing Sentry DSN does not block implementation.
- Evaluation: the thresholds in `vaani-master-plan/09-QUALITY_GATES.md` section 5 are ratified.
- Models and credentials: no candidate model identifiers are prescribed or recorded, and no OpenRouter credential is available. Do not hardcode a model choice. Complete provider-facing code and offline tests, but record credentialed W2-02 execution, W2-03 before/after reports, INT-2, and pilot readiness as pending external acceptance.
- Human review: implement Hindi/Odia strings and the synthetic evaluation dataset now. Native-speaker and dataset review happens afterward and remains mandatory before the pilot.

This decision separates implementation completion from external acceptance. Missing credentials or reviewers do not justify claiming a gate passed, but they do not pause independent code work.

## W1-01 Completion Report

- Commit: `8836713`
- TASK: W1-01
- FILES CHANGED:
  - `app/agent/render.py` — created citation stripping sanitizer
  - `app/workers/inbound.py` — applied strip_citations to graph response
  - `app/channels/voice/session.py` — applied strip_citations to voice response
  - `tests/test_render.py` — 10 unit tests for citation stripping
  - `tests/test_inbound_loop.py` — added assertion for outbound message stored text
- SUMMARY:
  Implemented strip_citations in app/agent/render.py to remove [source_ref: ...] tags and cleanup whitespace. Applied the sanitizer after graph invocation in inbound.py and voice/session.py so patients never receive internal citation tags. Added unit and loop tests.
- TESTS RUN:
  - `uv run pytest -q tests/test_render.py tests/test_inbound_loop.py tests/test_output_grounding.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 17 passed
  - Full suite: 224 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_strip_citations_single`, `test_strip_citations_multiple`, `test_strip_citations_tag_only`, `test_strip_citations_hindi`, `test_strip_citations_odia`, `test_strip_citations_unclosed`, `test_strip_citations_empty_and_none`, `test_strip_citations_mid_sentence`, `test_strip_citations_case_insensitive`, `test_strip_citations_preserves_newlines`
  - `git grep -n "strip_citations" app/`: found in `app/agent/render.py`, `app/workers/inbound.py`, and `app/channels/voice/session.py`
- PENDING EXTERNAL GATES: none for W1-01

## W1-05 Completion Report

- Commit: `6affe7c`
- TASK: W1-05
- FILES CHANGED:
  - `app/booking/timefmt.py` — created tenant_timezone and format_local
  - `app/workers/inbound.py` — used format_local in booking_status branch instead of raw isoformat()
  - `tests/test_timefmt.py` — 6 unit tests covering local time formatting and timezone fallbacks
- SUMMARY:
  Created app/booking/timefmt.py providing format_local and tenant_timezone. Updated inbound.py booking_status branch to load the tenant and render appointments in local timezone formatted as '%a %d %b, %I:%M %p'.
- TESTS RUN:
  - `uv run pytest -q tests/test_timefmt.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 6 passed
  - Full suite: 230 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_format_local_morning_ist`, `test_format_local_date_rollover_ist`, `test_format_local_timezone_aware`, `test_tenant_timezone_default_when_none_or_missing`, `test_tenant_timezone_invalid_falls_back`, `test_tenant_timezone_valid`
  - `git grep -n "isoformat()" app/workers/inbound.py`: 0 matches
- PENDING EXTERNAL GATES: none for W1-05

## W1-03 Completion Report

- Commit: `eaa8120`
- TASK: W1-03
- FILES CHANGED:
  - `app/agent/tools/slots_get.py` — filter slots by lead time (min start >= now + booking_lead_minutes)
  - `app/booking/engine.py` — atomic hold_slot requires slot start > now
  - `tests/test_past_slot_guard.py` — 4 new tests for past/lead time slot guards
  - `tests/test_booking_journey.py` — moved fixture slot dates to future
  - `tests/test_booking_transitions.py` — added future start times to slot fixtures
  - `tests/test_browser_owner_acceptance.py` — moved fixture slots to future
  - `tests/test_generated_objectid_boundaries.py` — added future start times to slot fixtures
  - `tests/test_production_load_security_closure.py` — added future start time to slot fixture
  - `tests/test_two_clinic_whatsapp_acceptance.py` — moved fixture slots to future
- SUMMARY:
  Implemented past-slot guards in slots_get (respecting booking_lead_minutes, default 30, clamp 0..1440) and hold_slot (requiring start > now in atomic query). Reconciled test fixture slots with past dates into future dates while preserving every assertion.
- TESTS RUN:
  - `uv run pytest -q tests/test_past_slot_guard.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 4 passed
  - Full suite: 234 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_past_slot_not_listed_and_not_holdable`, `test_slot_in_10_min_not_listed_with_default_lead_but_holdable`, `test_slot_in_2_hours_listed_and_holdable`, `test_tenant_zero_lead_lists_slot_in_10_min`
- PENDING EXTERNAL GATES: none for W1-03

## W1-04 Completion Report

- Commit: `6a92612`
- TASK: W1-04
- FILES CHANGED:
  - `app/channels/whatsapp.py` — added send_cancel_confirmation interactive button message
  - `app/workers/inbound.py` — replaced immediate cancellation with button prompt and added _handle_cancel_action
  - `tests/test_cancel_confirmation.py` — 5 new tests for cancel prompt, keep, expiry, no-flow, and duplicate tap idempotency
  - `tests/test_booking_journey.py` — updated cancel journey to tap cancel:confirm button
  - `tests/test_two_clinic_whatsapp_acceptance.py` — updated cancel journey to tap cancel:confirm button
- SUMMARY:
  Implemented two-step cancellation requiring an explicit button tap (cancel:confirm) before invoking booking_cancel. Cancel intent saves cancel_flow with 30-minute expiry and sends interactive buttons. Added _handle_cancel_action before _handle_booking_action.
- TESTS RUN:
  - `uv run pytest -q tests/test_cancel_confirmation.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 5 passed
  - Full suite: 239 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_cancel_prompt_and_confirmation_flow`, `test_cancel_keep_leaves_booking_unchanged`, `test_cancel_confirm_with_no_flow_is_ignored`, `test_cancel_confirm_expired_31_minutes_later`, `test_duplicate_cancel_confirm_idempotency`
  - `git grep -n "booking_cancel(" app/workers/inbound.py`: called only at line 239 inside `_handle_cancel_action`
- INDEPENDENT REVIEW (§4):
  - Any remaining path that cancels without cancel:confirm? No; booking_cancel is only called in _handle_cancel_action after verifying action_id == "cancel:confirm".
  - Is the conversation state == "bot" filter on every write? Yes; both update_one calls in inbound.py filter by `{"_id": conversation_db_id, "state": "bot"}`.
  - Are operation keys deterministic and distinct? Yes; cancel-confirm:{message_id or conversation_id}, cancel-keep:{message_id or conversation_id}, cancel-result:{conversation_id}:{booking_id}.
  - Does a duplicate tap double-send? No; idempotent operation key and stage completion prevents double processing.
- PENDING EXTERNAL GATES: none for W1-04

## W1-10 Completion Report

- Commit: `edc8ea8`
- TASK: W1-10
- FILES CHANGED:
  - `app/workers/inbound.py` — added UNSUPPORTED_TYPES and UNSUPPORTED_REPLY, updated _store_inbound to accept message_type, updated _resolve_conversation to maintain last_msg_at, and handled unsupported media types in process_event
  - `tests/test_unsupported_media.py` — 5 new tests covering audio replies, deduplication, human state silence, reaction ignoring, and last_msg_at maintenance
- SUMMARY:
  Added polite reply to unsupported non-text WhatsApp messages (audio, image, video, document, sticker, location, contacts) while keeping silence on human takeover. Updated inbound conversation resolution to always record last_msg_at.
- TESTS RUN:
  - `uv run pytest -q tests/test_unsupported_media.py tests/test_inbound_loop.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 9 passed
  - Full suite: 244 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_audio_message_replies_once_with_unsupported_text`, `test_duplicate_audio_event_deduplicates_outbound`, `test_human_state_stores_media_without_outbound`, `test_reaction_is_ignored_and_not_stored`, `test_text_inbound_sets_last_msg_at`
- PENDING EXTERNAL GATES: none for W1-10

## W1-06 Completion Report

- Commit: `7a2ef09`
- TASK: W1-06
- FILES CHANGED:
  - `app/owner_api/routes.py` — mapped delivery exceptions (WindowClosedError, SuppressedRecipientError, AmbiguousDeliveryError, RuntimeError) to 409 and 502 with structured detail {"code", "message"}
  - `dashboard/src/App.tsx` — updated api() helper to extract detail.message when detail is an object
  - `tests/test_staff_reply_errors.py` — 4 new tests verifying error mapping and ensuring failed deliveries do not record Messages rows
- SUMMARY:
  Staff reply endpoint now returns structured HTTP error responses (409 for window_closed, suppressed, delivery_unknown; 502 for provider_error) instead of unhandled 500s. Updated the dashboard error unpacker to display detail.message cleanly.
- TESTS RUN:
  - `uv run pytest -q tests/test_staff_reply_errors.py tests/test_browser_owner_acceptance.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
  - `npm --prefix dashboard run lint ; npm --prefix dashboard run build`
- RESULTS:
  - Focused: 13 passed
  - Full suite: 248 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
  - Dashboard: built in 640ms, 0 lint errors
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_staff_reply_error_mapping` covering `window_closed` (409), `suppressed` (409), `delivery_unknown` (409), and `provider_error` (502).
- PENDING EXTERNAL GATES: none for W1-06

## W1-07 Completion Report

- Commit: `2da8542`
- TASK: W1-07
- FILES CHANGED:
  - `app/owner_api/routes.py` — defined SETTINGS_FIELDS and filtered get_settings_api to return only allow-listed fields
  - `tests/test_settings_allow_list.py` — test verifying sensitive keys (whatsapp, gstin, razorpay_account_id, secrets) are excluded and returned keys are a subset of SETTINGS_FIELDS
- SUMMARY:
  Restricted GET /api/settings to return only clinic-facing fields defined in SETTINGS_FIELDS (_id, name, timezone, plan, locale_default, wa_number, voice_number, landmark_line, location_pin, business_hours, holiday_calendar). Internal secrets and billing identifiers no longer reach the browser.
- TESTS RUN:
  - `uv run pytest -q tests/test_settings_allow_list.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
- RESULTS:
  - Focused: 1 passed
  - Full suite: 249 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
- DEVIATIONS FROM PACKET: none (Settings in dashboard/src/App.tsx reads only name, landmark_line, location_pin, and _id, which are all present in SETTINGS_FIELDS)
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_get_settings_allow_list_filters_sensitive_fields`
- PENDING EXTERNAL GATES: none for W1-07

## W1-11 Completion Report

- Commit: `2a91229`
- TASK: W1-11
- FILES CHANGED:
  - `app/owner_api/views.py` — created enrich_conversations and enrich_bookings helpers with batched lookups
  - `app/owner_api/routes.py` — applied enrichment helpers to list_conversations and list_bookings
  - `tests/test_owner_view_models.py` — test verifying enriched view models, join shapes, and cross-tenant isolation
- SUMMARY:
  Added view-model enrichment helpers in app/owner_api/views.py. GET /api/conversations now includes contact (id, name, phone), last_message_preview, last_msg_at with tenant timezone offset, and open_escalation flag. GET /api/bookings includes contact, start/end ISO strings with tenant timezone offset, and practitioner (id, name).
- TESTS RUN:
  - `uv run pytest -q tests/test_owner_view_models.py tests/test_owner_route_authorization.py`
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q`
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
- RESULTS:
  - Focused: 8 passed
  - Full suite: 250 passed, 4 skipped
  - Ruff & mypy: passed with 0 issues
  - Tenant isolation: verified (0 unscoped db calls)
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_owner_view_models_enrichment_and_cross_tenant_isolation`
- INDEPENDENT REVIEW (§4):
  - Is every query through a tenant-scoped accessor? Yes; Contacts(tenant_id), Escalations(tenant_id), Messages(tenant_id), Slots(tenant_id), Practitioners(tenant_id).
  - Could an id from tenant B join into tenant A? No; verified by cross-tenant negative check in test_owner_view_models_enrichment_and_cross_tenant_isolation.
  - Any N+1 beyond the preview lookup? No; batched $in lookups for all contacts, slots, practitioners, escalations.
  - PII added to /deliveries or /processing? No; /deliveries and /processing remain untouched and PII-free.
- PENDING EXTERNAL GATES: none for W1-11
 
+## W1-12 Completion Report
+
+- Commit: `8c25086`
+- TASK: W1-12
+- FILES CHANGED:
+  - `dashboard/src/App.tsx`
+- SUMMARY:
+  Added pure helpers `obj`, `contactLabel`, `timeAgo`, and `formatWhen` (Intl.DateTimeFormat en-IN). Updated Inbox list rows to display patient name/phone, preview message, relative timestamp (`timeAgo(last_msg_at)`), and "Needs staff" badge when `open_escalation` is true. Updated thread header with contact label and distinct phone. Updated Appointments table to `Patient | Date & time | Doctor | Service | Status | (action)`, showing practitioner name and formatted appointment time, removing `Customer reference`/`Patient reference` and `Source`.
+- TESTS RUN:
+  - `git grep -n ">now<" dashboard/src/App.tsx` (exit code 1, 0 matches)
+  - `git grep -n "Patient reference" dashboard/src/App.tsx` (exit code 1, 0 matches)
+  - `npm --prefix dashboard run lint; npm --prefix dashboard run build`
+  - `uv run pytest -q tests/test_browser_owner_acceptance.py`
+  - `uv run ruff check app/ tests/ ; uv run mypy app/`
+  - `uv run pytest -q`
+  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
+- RESULTS:
+  - Acceptance grep: 0 matches for `>now<` or `Patient reference`
+  - Dashboard lint & build: 0 errors, Vite bundle generated
+  - Focused pytest: 9 passed
+  - Full suite: 250 passed, 4 skipped
+  - Ruff & mypy: 0 issues
+  - Tenant isolation: verified (0 unscoped db calls)
+- DEVIATIONS FROM PACKET: none
+- REMAINING ISSUES: none
+- EVIDENCE:
+  - Tests: `tests/test_browser_owner_acceptance.py`
+- PENDING EXTERNAL GATES: none for W1-12
 
## W1-02 Completion Report

- Commit: `645d03a`
- TASK: W1-02
- FILES CHANGED:
  - `app/agent/tenant_context.py` — created get_tenant_profile helper (name & business_type with fallback and sanitization)
  - `app/agent/nodes/responder.py` — system prompt dynamically inserts tenant name from get_tenant_profile
  - `app/agent/nodes/intent.py` — replaced 'weather in bhubaneswar' with 'weather today' in few-shot example
  - `app/agent/nodes/output_gate.py` — removed '|bhubaneswar' from location pattern regex
  - `app/agent/templates/README.md` — removed dead 'location_landmark' reference
  - `tests/test_no_tenant_literals.py` — scan for prohibited literals across app/agent excluding llm.py, and prompt verification test
- SUMMARY:
  Dehardcoded clinic identity and prohibited literals across all agent code. Created get_tenant_profile in app/agent/tenant_context.py to fetch and sanitize tenant name and business type. Updated responder prompt to introduce itself with the dynamic tenant name while keeping Grounded Facts citation structures intact. Removed Bhubaneswar literal from intent and output gate regex.
- TESTS RUN:
  - `uv run pytest -q tests/test_no_tenant_literals.py` (3 passed)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25, 100% accuracy, 0 hallucinations, 0 ungrounded)
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q` (253 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
- RESULTS:
  - Prohibited literal scan: 0 matches in app/agent/ (excluding llm.py)
  - Mock evals: 25/25 passed across all 4 languages (EN, HI, HI-LATN, OR)
  - Full test suite: 253 passed, 4 skipped
  - Ruff & mypy: 0 issues
  - Tenant isolation: verified (0 unscoped db calls)
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_no_hardcoded_tenant_literals_in_agent_code`, `test_responder_system_prompt_uses_tenant_name_and_no_intent_or_classify`, `test_get_tenant_profile_fallback_and_sanitization`
  - Mock eval report: `artifacts/mock-eval-report.json`
- PENDING EXTERNAL GATES:
  - Live model evals against OpenRouter credentials (pending external model credentials)

## W1-08 Completion Report

- Commit: `9b42ce1`
- TASK: W1-08
- FILES CHANGED:
  - `app/config.py` — added `enable_voice`, `enable_payments`, `enable_billing` (bool, default False); restructured `validate_runtime()` to conditionally require voice/payments/billing settings; dropped unused `bsp_*` from required list (kept fields).
  - `app/main.py` — conditional router mounts for Exotel and Razorpay based on feature flags; `create_app` accepts optional `Settings`.
  - `.env.example` — added `ENABLE_VOICE=false`, `ENABLE_PAYMENTS=false`, `ENABLE_BILLING=false`; updated `JWT_SECRET=` (no default) and `INVOICE_SAC_CODE=998313`.
  - `tests/conftest.py` — setdefault `ENABLE_VOICE`, `ENABLE_PAYMENTS`, `ENABLE_BILLING` to `true` so suite exercises all routes.
  - `tests/test_fixed_findings.py` — enabled flags on `valid` settings fixture so full credential validations remain asserted.
  - `tests/test_production_load_security_closure.py` — enabled flags on `valid` settings fixture so full credential validations remain asserted.
  - `tests/test_feature_flags.py` — unit and integration tests for feature flags, validation errors, and router mounting.
- SUMMARY:
  Implemented feature-flagged runtime validation allowing staging/prod to boot with WhatsApp-only configuration when voice, payments, and billing flags are off. Verified `bsp_access_token`, `bsp_waba_id`, and `bsp_phone_number_id` are read nowhere outside `app/config.py` and dropped them from the required validation list while retaining field declarations.
- TESTS RUN:
  - `uv run pytest -q tests/test_feature_flags.py tests/test_fixed_findings.py tests/test_production_load_security_closure.py` (22 passed)
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q` (260 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
- RESULTS:
  - Focused tests: 22 passed
  - Full test suite: 260 passed, 4 skipped
  - Ruff & mypy: 0 issues
  - Tenant isolation: verified (0 unscoped db calls)
- INDEPENDENT REVIEW (§4):
  - Staging with flags off boots with WhatsApp + LLM alone? Yes (`test_whatsapp_only_staging_boots_with_flags_off`).
  - Flags on with missing keys raise and name the missing keys? Yes (`test_enable_voice_without_exotel_raises_naming_missing_settings`, `test_enable_voice_with_sarvam_requires_sarvam_api_key`, `test_enable_billing_without_gstin_raises_naming_missing_settings`).
  - Default JWT secret still rejected with flags off? Yes (`test_default_jwt_secret_rejected_with_all_flags_off`).
  - Exotel/Razorpay routers unmounted when flags are off? Yes (`test_router_mounting_respects_feature_flags`).
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_feature_flags.py`, `test_fixed_findings.py`, `test_production_load_security_closure.py`
- PENDING EXTERNAL GATES: none for W1-08

## W1-09 Completion Report

- Commit: `76ceb5f`
- TASK: W1-09
- FILES CHANGED:
  - `Dockerfile` — added `COPY ops ./ops` before non-root chown
- SUMMARY:
  Copied `ops/` operator directory into the container image immediately following dashboard dist copy and preceding user ownership assignment (`chown -R appuser:appgroup /srv`). This makes operational CLI utilities (tenant onboarding, DPDP erasure, secret rotation, migration) runnable in production container environments.
- TESTS RUN:
  - `uv run python -m ops.onboard_tenant --help` (exited 0, usage text printed)
  - `docker info` / `docker build -t vaani:w1-09 .`
- RESULTS:
  - Local module check: passed (exit 0)
  - Docker build & container run: not verified — Docker unavailable (Docker Desktop daemon not running)
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Dockerfile diff: line 37 `COPY ops ./ops`
- PENDING EXTERNAL GATES:
  - Container build verification on Docker-enabled runner / CI










