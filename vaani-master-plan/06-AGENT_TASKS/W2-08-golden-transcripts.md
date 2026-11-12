### TASK ID: W2-08

> **Baseline note:** written against `847d5f5` with Wave 1, W2-01 and W2-03 merged; locate code by symbol name.

**Title:** Golden multi-turn transcript tests in four languages

**Priority:** P1

**Objective:** A data-driven test suite replays scripted WhatsApp conversations through `process_event` and asserts the exact kind and content of every outbound message, for eight journeys in each of the four languages.

**Why This Matters:** Existing tests check pieces. Nothing checks a whole conversation the way a patient experiences it, per language, so regressions such as an English button in a Hindi conversation or a leaked internal tag would pass CI.

**Prerequisites:** W2-01 (localized copy), W2-03 (final flow shape), all of Wave 1.

**Repository Context:**
- Entry point: `app/workers/inbound.py::process_event(fields)` with `fields = {"tenant_id", "message_id", "payload": json.dumps(<Meta webhook payload>)}`.
- Payload shapes are parsed by `_parse_message`: text → `messages[0] = {"from", "id", "type": "text", "text": {"body"}}`; list tap → `{"type": "interactive", "interactive": {"list_reply": {"id", "title"}}}`; button tap → `{"type": "interactive", "interactive": {"button_reply": {"id", "title"}}}`; audio → `{"type": "audio", "audio": {...}}`. `value.contacts[0].profile.name` carries the display name.
- All sends go through `app/channels/whatsapp.py::_post(tenant_id, wa_id, body, operation_key)`; under mock adapters it returns a fake id without network. `body["type"]` is `text`, `interactive` (with `interactive.type` `list` or `button`) or `template`.
- Tests run with the mock LLM. It recognises only certain keywords (see `app/agent/llm.py::get_mock_response`): e.g. `book`/`appointment`/`अपॉइंटमेंट`/`बुक`/`ଦେଖା କରିବି`, `cancel`/`radd`, `status`, `fee`/`फीस`/`ଫିସ୍`, `timing`/`समय`/`ସମୟ`, `dard`/`दर्द`/`ଯନ୍ତ୍ରଣା`. Scripted utterances must contain a recognised keyword **and** be in the target script so language detection picks the right language.
- Existing fixtures for tenants, practitioners, slots and KB: `tests/conftest.py`, `tests/test_two_clinic_whatsapp_acceptance.py`.
- Language is detected from script: Devanagari → `hi`, Odia → `or`, Latin with Hinglish markers (`hai`, `kya`, `mujhe`, `kal`, …) → `hi-Latn`, else `en`.

**Files to Inspect:** the files above; `app/i18n/strings.py`; `tests/test_booking_journey.py`

**Files to Modify/Create:**
- `tests/golden/README.md` — scenario format.
- `tests/golden/<journey>.<lang>.json` — 8 journeys × 4 languages = 32 files.
- `tests/test_golden_transcripts.py` — runner (parametrized over the files).
- `tests/golden_support.py` — payload builders and the outbound recorder.

**Detailed Implementation Instructions:**
1. **Recorder:** a fixture that monkeypatches `app.channels.whatsapp._post` with a wrapper that appends `{"to": wa_id, "body": body, "operation_key": operation_key}` to a list and then calls the original.
2. **Scenario format:**
```json
{
  "lang": "hi",
  "tenant": {"name": "Asha Clinic", "locale_default": "hi"},
  "steps": [
    {"send": {"text": "अपॉइंटमेंट बुक करना है कल"}},
    {"expect": [{"kind": "list", "button_key": "ui.choose_time", "min_rows": 1}]},
    {"send": {"tap": "slot:first"}},
    {"expect": [{"kind": "buttons", "ids": ["booking:confirm", "booking:cancel"],
                 "body_key": "booking.confirm_prompt"}]},
    {"send": {"tap": "booking:confirm"}},
    {"expect": [{"kind": "text", "key": "booking.booked"}]}
  ],
  "final": {"bookings_confirmed": 1}
}
```
   - `send.text`, `send.tap` (`slot:first` / `slot:last` resolve against the most recent recorded list rows; any other value is sent as-is), `send.media` (`"audio"` etc.).
   - `expect` lists the outbound messages produced by the preceding `send`, in order. `kind` ∈ `text | list | buttons | template | none`. Matching options: `key` / `body_key` / `button_key` (the i18n key whose **language-specific template** the text must match — compile the template to a regex by escaping it and replacing each `{param}` with `.+`), `contains`, `ids`, `min_rows`.
   - `final` checks: `bookings_confirmed`, `bookings_cancelled`, `conversation_state`, `open_escalations`.
3. **Global assertions applied by the runner to every outbound text/interactive body in every scenario:** no `[source_ref`; contains the scenario tenant's name wherever a clinic name appears and never `Sharma`; no ISO-8601 datetime pattern (`\d{4}-\d{2}-\d{2}T`); interactive titles within WhatsApp limits (button ≤ 20, row ≤ 24); for non-English scenarios, deterministic flow messages equal the target-language string (enforced through `key` matching).
4. **Journeys (each in `en`, `hi`, `hi-Latn`, `or`):**
   1. `faq_fees` — fee question → one text containing the seeded fee.
   2. `book_confirm` — book tomorrow → list → tap first → buttons → confirm → booked.
   3. `book_choose_again` — … → buttons → `booking:cancel` → list again.
   4. `status` — after a booking, status request → `status.found`.
   5. `cancel_confirm` — after a booking, cancel → buttons → `cancel:confirm` → `cancel.done`; one cancelled booking.
   6. `cancel_keep` — … → `cancel:keep` → `cancel.kept`; booking still confirmed.
   7. `medical_refusal` — medical question → the `medical_refusal` template text for that language; conversation state `human`; one open escalation.
   8. `unsupported_media` — audio → `media.unsupported`.
5. Use a fixed, future-relative slot fixture (slots tomorrow at several times) so pickers are never empty; give each scenario its own tenant id and patient number to avoid cross-talk.
6. Give every `send` a unique message id (`f"wamid.{scenario}.{index}"`).
7. If a scenario cannot pass because the **product** misbehaves (not the script), do not weaken the expectation: mark that parametrized case `xfail(strict=True)` with the reason and list it in your report under REMAINING ISSUES.

**Interfaces & Data Contracts:** the scenario JSON format above, documented in `tests/golden/README.md`.

**Edge Cases:** the mock classifier returning a different intent for a translated utterance → change the utterance to include a recognised keyword, and note it; outbound staff-alert templates (escalation) appear in the recorder with `kind: template` addressed to the staff number — expect them explicitly in journey 7.

**Non-Goals:** No changes under `app/`. No real-model calls. No screenshot or browser testing. No new product behaviour.

**Acceptance Criteria:** 32 scenarios collected; all pass or are `xfail(strict)` with a written reason (target: zero xfails); runtime under 60 s; full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_golden_transcripts.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Low (tests only). The risk is brittleness: matching on i18n keys rather than literal strings keeps copy edits from breaking the suite. Rollback = delete the files.

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** More than four scenarios need `xfail`; a journey is impossible under the mock LLM in some language; the suite needs a change under `app/` to become testable.

**Standalone Execution Prompt:**
```
Task W2-08 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet. Tests only - do not edit
anything under app/.
Build a data-driven transcript suite:
- tests/golden_support.py: Meta payload builders (text, list tap, button tap, media) and a fixture
  that wraps app.channels.whatsapp._post to record {to, body, operation_key} then calls the original.
- tests/golden/<journey>.<lang>.json in the format shown in the packet, for 8 journeys
  (faq_fees, book_confirm, book_choose_again, status, cancel_confirm, cancel_keep,
  medical_refusal, unsupported_media) x 4 languages (en, hi, hi-Latn, or). Utterances must be in
  the target script AND contain a keyword the mock LLM recognises (read get_mock_response).
- tests/test_golden_transcripts.py: parametrized runner calling process_event per step, resolving
  "slot:first"/"slot:last" from the last recorded list, matching expectations by i18n key
  (template -> regex), and applying the global assertions: no "[source_ref", no "Sharma", no ISO
  datetime, WhatsApp length limits.
- tests/golden/README.md documenting the format.
If the product (not your script) fails an expectation, mark that case xfail(strict=True) with the
reason and report it; never weaken the expectation.
Run: uv run pytest -q tests/test_golden_transcripts.py && uv run ruff check . && uv run pytest -q
Stop and report if more than four cases need xfail.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
