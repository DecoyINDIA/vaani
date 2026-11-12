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


