### TASK ID: W2-03

> **Owner execution decision (12 November 2026):** implement and independently review this packet even though no credentialed W2-02 baseline can be produced in this run. The missing before/after reports remain an explicit external acceptance gate: they block INT-2 and pilot readiness, but do not block the implementation commit. Do not hardcode or prescribe a model identifier.

> **Baseline note:** written against `847d5f5` with Wave 1, W2-04, W2-02 and W2-01 merged; locate code by symbol name.

**Title:** One structured "understand" call with conversation context; skip the responder on booking paths

**Priority:** P1

**Objective:** The classifier call returns intent **plus** requested date, time and optional doctor/service hints, using the last three turns as context. Booking-type intents on WhatsApp no longer make a second LLM call. The keyword date parser becomes a validator and fallback.

**Why This Matters:** The classifier sees one message with no history, so "kal" in answer to "which day?" is unintelligible. Requested time of day is ignored (the picker always shows the first ten slots). And every booking message pays for a responder call whose output is discarded in favour of the slot picker.

**Prerequisites:** W2-04 (JSON mode), W2-02 (harness implemented; credentialed baseline pending under the owner execution decision above), W2-01 (`t()`), W1-13.

**Repository Context:**
- `app/agent/nodes/intent.py`: after W2-02 has `build_intent_prompts(text, lang, business_type)` and `parse_intent_response(raw)`; the node returns `{"intent", "confidence"}` (+ `agent_error` on failure).
- `app/agent/state.py::AgentState` (TypedDict, `total=False`).
- `app/agent/nodes/tool_router.py`: for `book`/`reschedule` computes `target_date = resolve(text, today=…, lang=lang)`, takes the first practitioner, calls `slots_get`, appends a `slots_get` tool result.
- `app/agent/graph.py`: `tool_router → (handoff | responder)`; `responder → (handoff | output_gate)`.
- `app/workers/inbound.py::process_event`: after the graph, handles `booking_status`, `cancel`, `book`, `reschedule` itself; when `book`/`reschedule` has no slots it falls through and sends the graph's `response` (LLM text).
- `app/channels/voice/session.py` also runs the graph and **does** need the responder's text for booking intents (voice has no pickers). State carries `channel: "wa" | "voice"`.
- `app/booking/relative_date.py::resolve` returns `today` when nothing matches (cannot signal "no date found").
- **Mock coupling:** the mock extracts the user message with the greedy regex `(?:user message|patient latest message): '(.*)'` (DOTALL) — everything up to the **last** apostrophe in the prompt. Therefore `User message: '…'` must be the **final line** of the classifier user prompt; put history above it. The mock returns only `{"intent", "confidence"}` — missing optional fields must be tolerated.

**Files to Inspect:** the files above; `app/models/collections.py` (`Messages`), `evals/run_real_eval.py`, `tests/test_inbound_loop.py`, `tests/test_booking_journey.py`

**Files to Modify/Create:** `app/agent/nodes/intent.py`, `app/agent/state.py`, `app/agent/nodes/tool_router.py`, `app/agent/graph.py`, `app/booking/relative_date.py` (add `resolve_or_none`), `app/workers/inbound.py` (no-slots reply only), `app/i18n/strings.py` (one key), `evals/run_real_eval.py` (score the model's date), `tests/test_understand.py` (new).

**Detailed Implementation Instructions:**
1. **State:** add optional keys `req_date: str` (`YYYY-MM-DD`), `req_time: str` (`HH:MM`), `practitioner_hint: str`, `service_hint: str`.
2. **Prompt** (`build_intent_prompts` gains keyword parameters `today_iso: str`, `weekday: str`, `history: str = ""`): keep all existing guidance and few-shots; add to the **system** prompt the output contract — a JSON object with keys `intent`, `confidence`, `date` (`YYYY-MM-DD` or null), `time` (24-hour `HH:MM` or null), `practitioner_hint` (string or null), `service_hint` (string or null) — and the rules: resolve relative dates against "Today is {weekday}, {today_iso}"; ambiguous "kal" means **tomorrow**; never output a past date; null when the patient gave none. User prompt layout:
```
Language detected: {lang}
Recent conversation (oldest first):
{history or "(none)"}
User message: '{text}'
```
3. **History** (in the node, not the pure builder): last 6 messages of the conversation from `Messages(tenant_id)` sorted by `ts`, rendered `Patient: …` / `Clinic: …`, each truncated to 200 characters, apostrophes replaced with `’` (protects the mock regex). On any error use `""`.
4. **Parsing:** `parse_understanding(raw, *, today: date) -> dict` returns `intent`, `confidence` and the optional fields. Validation: unknown intent → `out_of_scope`/0.0 (as today); `date` must parse and satisfy `today ≤ date ≤ today + 90 days`, else dropped; `time` must match `^([01]\d|2[0-3]):[0-5]\d$`, else dropped; hints trimmed to 60 characters. Keep `parse_intent_response` as a thin wrapper for existing callers.
5. **Node:** load tenant timezone (default `Asia/Kolkata`) to compute `today`; return intent/confidence plus whichever optional keys validated.
6. **`relative_date.resolve_or_none(phrase, *, today, lang) -> date | None`:** same matching as `resolve`, but `None` where `resolve` would fall back to `today` without a match (an explicit "today/aaj" still returns `today`). Implement `resolve` in terms of it.
7. **`tool_router`** date choice, in order: valid `state["req_date"]` → `resolve_or_none(text)` → tenant-local today. If `req_time` is present, sort the `slots_get` result by absolute distance of each slot's local start time from `req_time` (ties: earlier first) before appending the tool result. Put `req_date`/`req_time` used into the tool result (`"date"`, `"requested_time"`).
8. **Graph:** after `tool_router`, route to `END` when `not escalate` **and** `state.get("channel") == "wa"` **and** intent ∈ `{book, reschedule, cancel, booking_status}`; otherwise as today. Voice is unchanged.
9. **`inbound.py`:** in the `book`/`reschedule` branch, when there is no slot result with slots (and, for reschedule, a booking exists), set `response = t("booking.no_slots", lang, date=…)` using a human date. Add the key `booking.no_slots`: "No appointments are available on {date}. Please send another day." in four languages (add `hi`/`or` to `docs/i18n-review.md`).
10. **Eval:** in `evals/run_real_eval.py`, for `date` rows also score the model's `date` field (new metric `model_date_accuracy`) alongside the parser metric.
11. **Tests (mock LLM unless stated):** `parse_understanding` accepts full, partial and intent-only JSON; drops past, far-future and malformed dates and bad times; prompt builder ends with the `User message:` line and contains today's date; history apostrophes are neutralized; `tool_router` prefers `req_date`, falls back to the parser, then today; slots re-ordered around `req_time`; on WhatsApp a `book` message triggers exactly **one** `query_llm` call (count via monkeypatch) and voice still triggers two; no-slots day yields the `booking.no_slots` text.

**Interfaces & Data Contracts:**
```json
{"intent": "book", "confidence": 0.93, "date": "2026-11-13", "time": "17:00",
 "practitioner_hint": null, "service_hint": "cleaning"}
```
Compatibility: a response containing only `intent` and `confidence` is valid.

**Edge Cases:** model returns a date that disagrees with an explicit keyword in the text (e.g. text says "parso", model says tomorrow) → prefer the **parser** when `resolve_or_none` matches an explicit relative keyword and the two differ, and log the disagreement at INFO without the text; history fetch failure; `req_time` with no slots near it → still show the nearest ten.

**Non-Goals:** No practitioner/service pickers (W3-03 uses the hints later). No change to scope-gate rules or the responder prompt. No change to voice behaviour. No prompt tuning beyond the additions above.

**Acceptance Criteria:**
- All tests pass; mock eval 25/25.
- Real-model eval (operator run, same models as the W2-02 baseline): per-language intent F1 not lower than baseline by more than 0.01; `model_date_accuracy ≥ 0.95`; safety recall 1.0; grounding violations 0. Attach both reports.
- `llm_calls` shows one call per WhatsApp booking turn.

**Verification:**
```bash
uv run pytest -q tests/test_understand.py tests/test_inbound_loop.py tests/test_booking_journey.py
uv run ruff check . && uv run mypy app && uv run pytest -q
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json
```
Operator: `uv run python evals/run_real_eval.py --ci --report artifacts/real-eval-after-w2-03.json`

**Risk & Rollback:** High — this changes what the model is asked and the graph's shape. The safety path must be provably untouched: the review checklist is (a) `scope_gate` still precedes every route to `responder`; (b) no new edge reaches `responder` for `medical_question`/`out_of_scope`/`abuse`/`complaint`; (c) the model's date is range-validated before use. Rollback = revert; no data migration.

**Effort & Complexity:** Large effort, high reasoning.

**Recommended Agent Tier:** Advanced agent required; independent review required.

**Escalation Conditions:** Existing tests assert the LLM-written text for booking intents on WhatsApp; the mock eval drops; or a future credentialed run shows real-model safety recall below 1.0. Absence of credentials or baseline numbers in this implementation run is recorded as pending acceptance and is not an implementation stop.

**Standalone Execution Prompt:**
```
Task W2-03 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this entire packet first; this is a
high-risk change and every numbered instruction matters.
Summary: extend the intent classifier into a structured "understand" step.
- AgentState: add req_date, req_time, practitioner_hint, service_hint.
- intent.py: prompt adds today's date/weekday (tenant timezone), the last 6 messages as history
  placed ABOVE the final line "User message: '<text>'" (that line must stay last; replace
  apostrophes in history), and a JSON contract with optional date/time/hints.
  parse_understanding() validates: intent in taxonomy, date within [today, today+90], HH:MM time;
  intent-only JSON remains valid (the mock LLM returns only intent+confidence).
- relative_date.py: add resolve_or_none(); resolve() delegates to it.
- tool_router.py: date = req_date, else resolve_or_none(text), else today; if the parser matched
  an explicit keyword and disagrees with the model, use the parser. Sort slots by closeness to
  req_time when present.
- graph.py: after tool_router go to END when channel == "wa", not escalated, and intent is
  book/reschedule/cancel/booking_status. Voice keeps the responder. Do not add any edge into
  responder and do not change scope_gate.
- inbound.py: when a book/reschedule request has no slots, reply with
  t("booking.no_slots", lang, date=...) (add the key in 4 languages; add hi/or to the review doc).
- evals/run_real_eval.py: add model_date_accuracy.
- tests/test_understand.py per the packet, including "exactly one query_llm call for a WhatsApp
  book message".
Run: uv run ruff check . && uv run mypy app && uv run pytest -q && the mock eval (25/25).
Commit the implementation after its offline gates and independent review pass. Record the missing
before/after real-model eval reports as pending external acceptance; do not claim INT-2 or pilot
readiness without them. Stop on any other escalation condition.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
