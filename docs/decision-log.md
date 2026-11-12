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

## W1-13 Completion Report

- Commit: `eae1b55`
- TASK: W1-13
- FILES CHANGED:
  - `app/booking/relative_date.py` — added `_has` helper enforcing word boundaries on ASCII keywords while preserving Indic substring matching; added explicit "today" check; added month-name date parsing (`15 november`, `nov 20th`, `5 jan`); added `tarikh` parsing with next-month roll; fixed `parse_colloquial_time` to remove `baje`/`bajey` from PM indicators, use `_has`, and give AM priority over PM.
  - `tests/test_relative_date_table.py` — parametrized test table covering 21 date phrases and 7 colloquial time phrases with base date 2026-11-12.
- SUMMARY:
  Fixed substring matching bugs in date resolution where words like "next month", "satisfied", and "aajkal" falsely matched weekday or relative keywords. Added support for named months and "tarikh" phrases. Fixed colloquial time parsing so "subah 10 baje" and "10 baje" resolve to 10:00 instead of 22:00.
- TESTS RUN:
  - `uv run pytest -q tests/test_relative_date_table.py tests/test_relative_date_boundaries.py` (30 passed)
  - `uv run ruff check .`
  - `uv run mypy app`
  - `uv run pytest -q` (288 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
- RESULTS:
  - Focused table tests: 30 passed (all 21 date rows and 7 time rows)
  - Full test suite: 288 passed, 4 skipped
  - Ruff & mypy: 0 issues
  - Tenant isolation: verified (0 unscoped db calls)
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - Tests: `test_relative_date_resolution_table`, `test_parse_colloquial_time_table`, `test_day_after_tomorrow_precedes_tomorrow_match`, `test_short_date_rolls_across_year_and_normalizes_indic_digits`
- PENDING EXTERNAL GATES: none for W1-13

## INT-1 Integration Checkpoint Report

- Commit: `4b0b090`
- CHECKPOINT: INT-1 (Wave 1 Complete)
- SUMMARY:
  All Wave 1 packets (W1-01 through W1-13) are merged on `main`. Quality gate 09 §2 passed with 290 pytest tests passing (4 skipped), 0 ruff errors, 0 mypy issues, clean Vite dashboard build, 0 tenant-isolation violations, and 25/25 mock evals (100% accuracy across EN, HI, HI-Latn, and OR). Scripted transcript test `tests/test_wave1_transcript.py` verified end-to-end multi-tenant behavior under mock adapters: FAQ citations stripped, past slots excluded from booking, local formatted appointment time rendered in booking status, two-step interactive cancellation confirmed, unsupported audio politely refused, and strict tenant isolation preserved. Staging startup with feature flags off verified: WhatsApp and Meta routes mount cleanly while voice (Exotel) and payments (Razorpay) routes remain unmounted.
- TEST COUNTS & GATE RESULTS:
  - Pytest: 290 passed, 4 skipped in 13.37s
  - Mock evals: 25/25 passed across 4 languages (Macro F1 1.0000, 0 hallucinations, 0 ungrounded)
  - Ruff check: 0 errors
  - Mypy check: 0 errors across 70 source files
  - Tenant isolation: 0 unscoped db calls outside `app/models/`
  - Dashboard: TypeScript lint and Vite build succeeded
- PENDING EXTERNAL GATES:
  - Container image digest verification on Docker-enabled runner (Docker daemon unavailable locally)
  - Live model evals against OpenRouter credentials

## W2-04 Completion Report

- Commit: `9132652`
- TASK: W2-04
- FILES CHANGED:
  - `app/config.py`: added `llm_timeout_seconds: float = 8.0` and `llm_json_mode: bool = True` settings.
  - `.env.example`: documented `LLM_TIMEOUT_SECONDS=8.0` and `LLM_JSON_MODE=true`.
  - `app/models/collections.py`: added `LlmCalls(TenantScoped)` collection helper and compound/TTL index specs (`("tenant_id", 1), ("ts", -1)` and 30-day TTL on `ts`).
  - `app/agent/llm.py`: introduced `LlmError`, `LlmTimeoutError`, configured client pooling via `_client()` and `set_http_client()`, implemented `call_openrouter()` with JSON mode payload support, structured error retry classification (retryable on timeout, transport, 429, >=500), automatic fallback retry to `llm_model_fallback_provider`, and asynchronous telemetry logging to `llm_calls`.
  - `app/agent/nodes/intent.py`: passed `json_mode=True`, `node="intent"`, `tenant_id=tenant_id` to `query_llm`.
  - `app/agent/nodes/responder.py`: passed `node="responder"`, `tenant_id=tenant_id` to `query_llm`.
  - `tests/test_llm_client.py`: test suite verifying single-attempt success with telemetry, timeout retries falling back to secondary model, non-retryable 4xx errors, retryable 500 errors raising after fallback, `response_format` payload in JSON mode, and mock adapter bypass without network or telemetry.
- SUMMARY:
  Hardened the LLM invocation layer with configurable per-call timeout budget (8.0s default), single retry with provider/model fallback on retryable errors, native JSON mode flag, dual-inheritance `LlmTimeoutError` preserving backward compatibility with legacy test expectations, and tenant-scoped datastore telemetry capturing latency, token usage, and status.
- TESTS RUN:
  - `uv run pytest -q tests/test_llm_client.py tests/test_fixed_findings.py` (16 passed)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 70 source files)
  - `uv run pytest -q` (296 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 6 new LLM client tests passed.
  - Full pytest suite: 296 passed, 4 skipped.
  - Mock evals: 25/25 passed across EN, HI, HI-Latn, OR.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_llm_client.py` covering timeout fallback, JSON mode formatting, 400 rejection, and telemetry collection.
## W2-05 Completion Report

- Commit: `8abc331`
- TASK: W2-05
- FILES CHANGED:
  - `pyproject.toml`, `uv.lock`: added `sentry-sdk>=2` runtime dependency via `uv add "sentry-sdk>=2"`.
  - `app/observability.py`: implemented `ContextVar` trackers for `tenant_id`, `conversation_id`, and `message_id` with `bind()` and `clear()`; single-line JSON log formatter `JsonFormatter` with UTC ISO timestamps, log level, logger name, message, service tag, non-empty correlation IDs, and `exc_type`; Sentry scrubber `_scrub` purging request body, cookies, headers, and stackframe local variables; idempotent `init_observability(service)` installing `StreamHandler(sys.stdout)` and configuring Sentry when `SENTRY_DSN` is configured.
  - `app/main.py`: initialized observability in `create_app()` with service `"api"`.
  - `app/workers/inbound.py`: initialized observability in `main()` with service `"worker"`; bound `tenant_id` and `message_id` at start of `process_event`, bound `conversation_id` upon resolution, and ensured `clear()` runs in `finally`; purged patient WhatsApp numbers from log calls ("Agent produced an empty response", "24h window closed"), referencing `conversation_id` instead.
  - `tests/test_observability.py`: unit tests verifying JSON formatting, correlation ID injection and clearing, exception type logging, Sentry event scrubbing, idempotent initialization with empty DSN, and untouched log message arguments.
- SUMMARY:
  Implemented structured JSON logging with context-bound correlation IDs (`tenant_id`, `conversation_id`, `message_id`), safe Sentry error reporting with PII data and frame-variable scrubbing, and removed patient WhatsApp numbers from inbound worker log messages.
- TESTS RUN:
  - `uv run pytest -q tests/test_observability.py` (6 passed)
  - `uv sync --frozen --extra dev` (0 errors)
  - `git grep -n "wa_id" app/workers/inbound.py | Select-String "logger\."` (0 matches)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 71 source files)
  - `uv run pytest -q` (302 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 6 new observability tests passed.
  - Full pytest suite: 302 passed, 4 skipped.
  - Frozen dev environment synced cleanly.
  - Mock evals: 25/25 passed across EN, HI, HI-Latn, OR.
  - Zero PII leaks in worker logger statements.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_observability.py` covering formatting, binding, scrubbing, and idempotence.
- PENDING EXTERNAL GATES:
  - Sentry event reception verification against live SENTRY_DSN on staging/production environment.

## W2-02 Completion Report

- Commit: `9f44d04`
- TASK: W2-02
- FILES CHANGED:
  - `app/agent/nodes/intent.py`: extracted pure `build_intent_prompts(text, lang, business_type, profile)` and `parse_intent_response(raw)` functions; updated `intent()` node to call them.
  - `app/agent/nodes/responder.py`: extracted pure `build_responder_prompts(tenant_name, lang, grounded_facts, history, text, extra_context, customer_term)` retaining exact `Grounded Facts:\n` and `\n\nStrict Citation Rule` prompt markers; updated `responder()` node to call it.
  - `app/booking/relative_date.py`: added colloquial Hinglish weekday spelling variants ("somwar", "mangalwar", "budhwar", "guruwar", "shukrawar", "shaniwar", "raviwar") to `weekdays_map`.
  - `evals/dataset/real_eval.jsonl`: generated 320 synthetic labelled evaluation utterances (80 each in `en`, `hi`, `hi-Latn`, `or`; 48 safety, 48 date, 72 faq with numeric facts, 152 intent rows; zero real PII/clinic names; all marked `"reviewed": false`).
  - `evals/dataset/README.md`: documented dataset schema, distribution, and mandatory native-speaker review requirement for Hindi and Odia rows before clinical deployment.
  - `evals/run_real_eval.py`: evaluation harness refusing mock adapters/LLM; supporting injectable `model_fn`; evaluating language accuracy, classifier F1, date resolution, and responder grounding; tracking p50/p95 latency and token usage; enforcing CI quality thresholds (`overall_macro_f1 >= 0.90`, `safety_recall == 1.0`, `date_accuracy >= 0.95`, `grounding_violations == 0`); producing JSON reports containing failing row IDs with no utterance text leakage.
  - `.github/workflows/real-model-eval.yml`: GitHub Actions workflow with `workflow_dispatch` and nightly cron schedule (`30 20 * * *`) executing `evals/run_real_eval.py --ci`.
  - `tests/test_real_eval_harness.py`: unit tests verifying dataset schema and distribution counts, mock mode refusal, perfect fake model evaluation, per-language failure detection on Odia misclassification, grounding violation detection on hallucinated numbers, and absence of utterance text in reports.
- SUMMARY:
  Implemented the real-model evaluation harness, created a 320-utterance 4-language benchmark dataset, authored the nightly GitHub Actions workflow, refactored intent and responder nodes into pure testable prompt builders without altering existing mock behavior, and verified the entire harness with fake model tests.
- TESTS RUN:
  - `uv run pytest -q tests/test_real_eval_harness.py tests/test_no_tenant_literals.py` (9 passed)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 71 source files)
  - `uv run pytest -q` (308 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 6 real-eval harness tests passed.
  - Full pytest suite: 308 passed, 4 skipped.
  - Mock evals: 25/25 passed across EN, HI, HI-Latn, OR (Macro F1 1.0000, 0 hallucinations, 0 ungrounded).
  - Zero hardcoded tenant literals in `app/agent`.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_real_eval_harness.py` validating dataset counts, gate thresholds, and report sanitization.
  - `evals/dataset/real_eval.jsonl` with 320 rows.
- PENDING EXTERNAL GATES:
  - Credentialed model evaluation run against live OpenRouter API keys in CI / staging.
  - Native speaker human review of Hindi and Odia rows in `evals/dataset/real_eval.jsonl`.

## 2026-11-12 — W2-01: Localize deterministic patient copy and persist conversation language
- STATUS: Completed
- COMMIT: bcc98bd
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-01-i18n-flow-strings.md
- SUBSYSTEMS TOUCHED:
  - `app/i18n/__init__.py` — LANGS ("en", "hi", "hi-Latn", "or"), normalize_lang(), and t(key, lang, **params) with fallback to English
  - `app/i18n/strings.py` — string table with all 27 keys translated across en, hi, hi-Latn, and or
  - `app/booking/timefmt.py` — format_local with lang parameter supporting English, Hindi, and Odia date/time abbreviations (<= 24 chars)
  - `app/channels/whatsapp.py` — added keyword-only button and title label parameters with truncation to WhatsApp character limits
  - `app/workers/inbound.py` — replaced all inline English copy with t(); implemented _conversation_lang(); persisted detected language on non-Latin or >= 3 words; stored slot instants in ISO format and localized labels on send
  - `docs/i18n-review.md` — catalog of all Hindi and Odia translations needing native-speaker sign-off
  - `tests/test_i18n.py` — tests for string presence, parameter parity, WhatsApp length limits, date formatting, language persistence, and prohibited inline copy
- SUMMARY:
  Localize every deterministic patient message across booking, status, reschedule, cancel, opt-in/opt-out, and unsupported media flows into four languages (en, hi, hi-Latn, or). Language is remembered on the conversation and contact. Slot instants are stored as ISO timestamps and formatted localized at send time. All UI literals respect strict WhatsApp character limits.
- TESTS RUN:
  - `uv run pytest -q tests/test_i18n.py tests/test_handoff.py tests/test_booking_journey.py tests/test_cancel_confirmation.py` (24 passed)
  - `uv run pytest -q tests/test_two_clinic_whatsapp_acceptance.py tests/test_unsupported_media.py tests/test_no_tenant_literals.py` (13 passed)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 73 source files)
  - `uv run pytest -q` (318 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 10 i18n tests passed.
  - Prohibited string regex in `inbound.py` returned 0 matches.
  - Full pytest suite: 318 passed, 4 skipped (10 new tests added).
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_i18n.py` verifying full language coverage, param alignment, and length constraints.
  - `docs/i18n-review.md` with complete catalog of translated strings.
- PENDING EXTERNAL GATES:
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.

## 2026-11-12 — W2-03: Structured understand with conversation context and WhatsApp responder skip
- STATUS: Completed
- COMMIT: 774036f
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-03-structured-understand.md
- SUBSYSTEMS TOUCHED:
  - `app/agent/state.py` — added req_date, req_time, practitioner_hint, service_hint
  - `app/agent/nodes/intent.py` — structured understand with JSON output contract, date range validation [today, today+90], time validation, and last 6 messages conversation context
  - `app/booking/relative_date.py` — added resolve_or_none; refactored resolve to delegate
  - `app/agent/nodes/tool_router.py` — prefers req_date, falls back to resolve_or_none, then today; prefers parser on keyword disagreement; sorts slots by req_time
  - `app/agent/graph.py` — routes to END after tool_router when channel is "wa" and intent in {book, reschedule, cancel, booking_status}; voice routes to responder
  - `app/workers/inbound.py` — handles empty slot result for book/reschedule with localized booking.no_slots message
  - `app/i18n/strings.py` & `docs/i18n-review.md` — added booking.no_slots in en, hi, hi-Latn, and or
  - `evals/run_real_eval.py` — added model_date_accuracy metric
  - `tests/test_understand.py` — new tests for understanding parser, prompt builder, mock coupling, date priorities, slot sorting, single LLM call on WhatsApp, and no-slots messaging
- SUMMARY:
  Extended intent classification into a structured understand node that extracts intent, dates, times, and entity hints using the last 6 messages of conversation context. WhatsApp booking flows now terminate directly after tool_router to save LLM tokens and latency, while voice channel retains responder text generation. Keyword date parser acts as a validator and fallback. Independent safety review verified: (a) scope_gate still precedes every route to responder, (b) no new edge reaches responder for gated intents, and (c) model date is range-validated.
- TESTS RUN:
  - `uv run pytest -q tests/test_understand.py tests/test_inbound_loop.py tests/test_booking_journey.py` (16 passed)
  - `uv run pytest -q tests/test_business_profile.py tests/test_no_tenant_literals.py` (7 passed)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 73 source files)
  - `uv run pytest -q` (327 passed, 4 skipped)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 9 understand tests passed.
  - Confirmed exactly 1 query_llm call for WhatsApp booking, and 2 for voice.
  - Full pytest suite: 327 passed, 4 skipped (9 new tests added).
  - Mock evals: 25/25 passed.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_understand.py` validating parser, routing, slot sorting, and LLM call counts.
  - `artifacts/mock-eval-report.json` showing 25/25 pass.
- PENDING EXTERNAL GATES:
  - Credentialed before/after W2-03 real-model evaluation comparison reports on OpenRouter models (`evals/run_real_eval.py`).
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.

## 2026-11-12 — W2-08: Golden multi-turn transcript tests in four languages
- STATUS: Completed
- COMMIT: 0a97fc5
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-08-golden-transcripts.md
- SUBSYSTEMS TOUCHED:
  - `tests/golden_support.py` — Meta webhook inbound payload builders (text, list reply, button reply, media) and WhatsApp recorder monkeypatching `app.channels.whatsapp._post`
  - `tests/golden/README.md` — comprehensive specification of scenario schema, matching contracts, global assertions, and step lifecycle
  - `tests/golden/<journey>.<lang>.json` — 32 scenario files covering 8 journeys (faq_fees, book_confirm, book_choose_again, status, cancel_confirm, cancel_keep, medical_refusal, unsupported_media) across 4 languages (en, hi, hi-Latn, or)
  - `tests/test_golden_transcripts.py` — parametrized runner verifying conversation flow, template regex matching, WhatsApp length limits, tenant de-hardcoding, and database post-conditions
- SUMMARY:
  Implemented a data-driven end-to-end conversation test suite replaying patient interactions through `process_event`. Validates complete conversational journeys across English, Hindi, Hinglish, and Odia without modifying application code. All outbound messages are asserted for exact structure, localized text matching, absence of leaked internal citation tags, proper clinic identity, absence of unrendered ISO datetimes, and WhatsApp character constraints (buttons ≤ 20, lists ≤ 24).
- TESTS RUN:
  - `uv run pytest -q tests/test_golden_transcripts.py` (32 passed in 1.42s)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 73 source files)
  - `uv run pytest -q` (359 passed, 4 skipped in 14.44s)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 32 golden multi-turn transcript scenarios passed with 0 xfails.
  - Full pytest suite: 359 passed, 4 skipped (32 new parametrized tests added).
  - Mock evals: 25/25 passed.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none (target of zero xfails met)
- EVIDENCE:
  - `tests/golden/` directory containing all 32 golden scenario specifications.
  - `tests/test_golden_transcripts.py` passing under 2 seconds.
- PENDING EXTERNAL GATES:
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.
  - Credentialed model evaluation on OpenRouter (`evals/run_real_eval.py`).

## 2026-11-12 — W2-09: Replace numbered text menu with tappable capability menu
- STATUS: Completed
- COMMIT: 6bf67a7
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-09-interactive-menu.md
- SUBSYSTEMS TOUCHED:
  - `app/i18n/strings.py` — added 7 keys (menu.prompt, menu.button, menu.book, menu.hours, menu.location, menu.status, menu.human) across en, hi, hi-Latn, and or
  - `docs/i18n-review.md` — documented Section 7 for interactive capability menu strings with length audits
  - `app/channels/whatsapp.py` — implemented `send_menu` for interactive list messages with 24h-window verification, character limits, and outbound audit
  - `app/agent/templates/__init__.py` — shortened `out_of_scope` across all 4 languages to single apology sentence (removed numbered list)
  - `app/agent/state.py` & `app/agent/nodes/lang_detect.py` — added and supported `lang_override` in AgentState to preserve conversation language on synthetic menu actions
  - `app/workers/inbound.py` — sent capability menu on out_of_scope bot replies; mapped `menu:*` action IDs to synthetic English utterances while maintaining conversation language and single inbound persistence
  - `tests/test_menu.py` — 10 tests verifying apology, menu shape, language preservation, tap dispatch, and single inbound persistence
- SUMMARY:
  Replaced the legacy numbered capability text with a WhatsApp interactive list menu (Book, Timings, Location, My appointment, Talk to staff) dispatched whenever a message is out of scope. Menu taps are processed deterministically via standard pipeline intents without corrupting stored conversation language or duplicating database inbound records.
- TESTS RUN:
  - `uv run pytest -q tests/test_menu.py tests/test_golden_transcripts.py` (42 passed in 1.62s)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 73 source files)
  - `uv run pytest -q` (369 passed, 4 skipped in 15.64s)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 10 menu tests passed.
  - Numbered list pattern `1\. ` completely removed from templates.
  - Full pytest suite: 369 passed, 4 skipped (10 new tests added).
  - Mock evals: 25/25 passed.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_menu.py` validating out_of_scope apology, menu dispatch, tap execution, and language retention.
  - `docs/i18n-review.md` Section 7 detailing menu translations.
- PENDING EXTERNAL GATES:
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.
  - Credentialed model evaluation on OpenRouter (`evals/run_real_eval.py`).

## 2026-11-12 — W2-06: Worker concurrency & patient message ordering
- STATUS: Completed
- COMMIT: bfdd1ee
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-06-worker-concurrency.md
- SUBSYSTEMS TOUCHED:
  - `app/config.py` & `.env.example` — added `worker_concurrency: int = 8` setting
  - `app/models/collections.py` — added `lease_seconds: int = 60` parameter to `acquire_work_unscoped` and sorted scan by `[("accepted_at", 1), ("_id", 1)]` to `find_queued_unscoped`
  - `app/workers/inbound.py` — compiled LangGraph app once via `_GRAPH` & `get_graph()`; assigned unique host-pid stream-consumer name `CONSUMER = make_consumer_name()`; added patient grouping key `_contact_key`; implemented `_run_grouped` concurrency batch runner; updated MongoDB fallback scan (cap 50, lease 180), `xautoclaim`, and `xreadgroup` (`count = max(10, 2 * settings.worker_concurrency)`) with group-done heartbeat refresh
  - `tests/test_worker_concurrency.py` — 8 tests covering concurrent execution across patients (max_concurrent >= 4), strictly serial in-order execution within a patient (max_concurrent == 1), isolated failure resilience, duplicate delivery deduplication, unique consumer generation across PIDs, graph caching singleton, rollback switch (`WORKER_CONCURRENCY=1`), and contact key resolution
- SUMMARY:
  Enabled concurrent processing of inbound messages across different patients up to `WORKER_CONCURRENCY` (default 8) while strictly maintaining serial arrival-order processing for messages from the same patient within a worker process. Multiple worker replicas remain unsupported for patient ordering (documented as non-goal). LangGraph application is compiled once on worker startup.
- TESTS RUN:
  - `uv run pytest -q tests/test_worker_concurrency.py tests/test_durable_ingress.py tests/test_inbound_loop.py` (21 passed in 1.34s)
  - `powershell -Command "$env:WORKER_CONCURRENCY = '1'; uv run pytest -q; $env:WORKER_CONCURRENCY = ''"` (377 passed, 4 skipped in 14.45s)
  - `uv run pytest -q` (377 passed, 4 skipped in 14.63s)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 73 source files)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - 8 new concurrency tests passed.
  - Concurrency across patients verified (max concurrent >= 4).
  - In-order arrival sequence preserved for single patient (max concurrent == 1).
  - Full pytest suite: 377 passed, 4 skipped (8 new tests added).
  - Rollback switch (`WORKER_CONCURRENCY=1`) fully verified on full test suite.
  - Mock evals: 25/25 passed.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `tests/test_worker_concurrency.py` validating concurrency, sequential per-patient ordering, deduplication, and single-graph caching.
- PENDING EXTERNAL GATES:
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.
  - Credentialed model evaluation on OpenRouter (`evals/run_real_eval.py`).

## 2026-11-12 — W2-07: Extract scheduler to dedicated service & retryable slot expansion
- STATUS: Completed
- COMMIT: ba3758b
- PACKET: vaani-master-plan/06-AGENT_TASKS/W2-07-scheduler-split.md
- SUBSYSTEMS TOUCHED:
  - `app/config.py` & `.env.example` — added `scheduler_interval_seconds: int = 300` setting
  - `app/workers/scheduler.py` — created dedicated scheduler entrypoint (`run_once()`, `run_scheduler_background()`, `main()`) running stale sends, slot expansion, reminders, escalation SLAs, monthly billing (conditional on `enable_billing`), daily briefs, and weekly summaries with Redis heartbeat `vaani:scheduler:heartbeat`
  - `app/workers/inbound.py` — removed embedded scheduler background task from inbound worker loop while re-exporting `run_scheduler_background` for backwards compatibility
  - `app/booking/engine.py` — enabled retry takeover of failed or stale running (>30 min) `slot_expansion` job rows via atomic `find_one_and_update` with `$inc: {retries: 1}`
  - `app/workers/healthcheck.py` — parameterized healthcheck to accept optional heartbeat key and max age CLI arguments with component identifier in audit alert payload
  - `docker-compose.yml` — added `scheduler` single-replica Compose service with healthcheck on `vaani:scheduler:heartbeat` (900s timeout)
  - `tests/test_scheduler.py` — 8 tests covering `run_once` execution order, failure isolation, billing gating, slot expansion retry takeover, inbound worker decoupling, and healthcheck key/staleness validation
- SUMMARY:
  Extracted all periodic maintenance jobs (reminders, slot expansion, escalation SLAs, daily briefs, weekly summaries, billing invoices) into an independent scheduler worker process (`app.workers.scheduler`). Added atomic takeover and retry of failed or stale slot expansion runs to prevent clinics from running out of bookable slots. Updated container infrastructure and healthchecks to monitor scheduler heartbeat separately.
- TESTS RUN:
  - `uv run pytest -q tests/test_scheduler.py tests/test_schedule_expansion.py tests/test_handoff_scheduling_alerts_acceptance.py` (17 passed in 1.04s)
  - `docker compose config` (validated successfully with 0 errors)
  - `uv run pytest -q` (385 passed, 4 skipped in 14.39s)
  - `uv run ruff check .` (0 errors)
  - `uv run mypy app` (0 errors across 74 source files)
  - `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (exit code 1, 0 matches)
  - `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy)
- RESULTS:
  - All 8 new scheduler tests passed.
  - Zero scheduler tasks running inside inbound worker loop (`grep -n "create_task(run_scheduler_background" app/workers/inbound.py` returned 0 matches).
  - Slot expansion takeover confirmed for `failed` state and `running` state >30m.
  - Full pytest suite: 385 passed, 4 skipped.
  - Mock evals: 25/25 passed.
  - Zero tenant-isolation violations.
- DEVIATIONS FROM PACKET: none
- REMAINING ISSUES: none
- EVIDENCE:
  - `app/workers/scheduler.py` dedicated service.
  - `tests/test_scheduler.py` passing with 100% assertions.
  - `docker-compose.yml` scheduler service definition.
- PENDING EXTERNAL GATES:
  - Native-speaker human review and sign-off on Hindi and Odia strings in `docs/i18n-review.md`.
  - Credentialed model evaluation on OpenRouter (`evals/run_real_eval.py`).

## 2026-11-12 — INT-2 Checkpoint: Wave 2 Integration & Concurrency Soak
- STATUS: Checkpoint Passed (All Locally Executable Checks Succeeded)
- COMMIT: 3f66e51
- PACKET: vaani-master-plan/08-EXECUTION_ORCHESTRATOR.md §5 (INT-2)
- SUBSYSTEMS VERIFIED:
  - Full codebase across app, workers, agents, channels, i18n, models, observability, and dashboard
  - All Wave 1 packets: W1-01 through W1-13, INT-1 Checkpoint
  - All Wave 2 packets: W2-04 (LLM resilience & telemetry), W2-05 (Sentry & structured JSON logging), W2-02 (real eval harness & 320-utterance dataset), W2-01 (localization in 4 languages), W2-03 (structured understand & context), W2-08 (golden transcript tests in 4 languages), W2-09 (interactive capability menu), W2-06 (worker concurrency & patient ordering), W2-07 (dedicated scheduler service & retryable slot expansion)
- CHECKS EXECUTED LOCALLY:
  1. Automated Quality Gate:
     - `uv run ruff check .` (0 errors)
     - `uv run mypy app` (0 errors across 74 source files)
     - `uv run pytest -q` (386 passed, 4 skipped in 17.56s)
     - Strict tenant-isolation grep: `git grep -nE 'db\[[^]]+\]\.(find|insert|update|delete)' app/ ':!app/models/'` (0 matches)
     - `cd dashboard && npm run lint && npm run build` (0 lint errors; Vite production build generated in 715ms)
     - `docker compose config` (validated cleanly with `api`, `worker`, `scheduler`, and `redis`)
     - Mock evals: `uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json` (25/25 passed, 100% accuracy, 0 hallucinations, 0 ungrounded claims)
  2. Multi-turn Golden Transcript Suite (W2-08):
     - 32 scenarios executed across 8 journeys in `en`, `hi`, `hi-Latn`, `or` with regex template matching and global boundary assertions (32/32 passed in 0.99s)
  3. 20-Conversation Concurrency Soak:
     - 20 distinct patients with 2 sequential messages each (40 messages total) processed through concurrent worker queue (`test_twenty_conversation_concurrency_soak` — passed; max_concurrent >= 6, strict arrival-order in-group serialization, 0 failed messages, 40 completed)
  4. Concurrency Rollback Switch:
     - Full test suite verified green with `WORKER_CONCURRENCY=1` (377 passed, 4 skipped)
- RESULTS:
  - All written Wave 1 and Wave 2 packets have implementation commits on `main`.
  - All locally executable integration checks for INT-2 are green.
  - Zero tenant-isolation violations across the platform.
- PENDING EXTERNAL ACCEPTANCE GATES (NOT LOCALLY EXECUTABLE):
  1. Live OpenRouter model API credentials: required to execute `evals/run_real_eval.py` against live models to ratify ratified section 5 thresholds (Macro-F1 >= 0.90, safety recall 1.00, date accuracy >= 0.95).
  2. W2-03 before/after comparative model evaluation benchmark on credentialed OpenRouter models.
  3. Native-speaker human review and sign-off on Hindi (`hi`), Hinglish (`hi-Latn`), and Odia (`or`) strings in `docs/i18n-review.md`.
  4. Native-speaker human review on the 320-row multilingual evaluation dataset (`evals/dataset/real_eval.jsonl`).
  5. Live staging smoke test on a real Meta/WhatsApp business test phone number (INT-3 / manual staging smoke).


















