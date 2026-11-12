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






