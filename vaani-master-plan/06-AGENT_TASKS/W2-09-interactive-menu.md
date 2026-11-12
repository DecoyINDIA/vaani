### TASK ID: W2-09

> **Baseline note:** written against `847d5f5` with Wave 1, W2-01 and W2-03 merged; locate code by symbol name.

**Title:** Replace the numbered text menu with a tappable capability menu

**Priority:** P1

**Objective:** When the bot does not understand a WhatsApp message, it sends a short apology plus a list menu (Book, Timings, Location, My appointment, Talk to staff). Each tap is handled deterministically and keeps the conversation's language.

**Why This Matters:** The out-of-scope template ends with "1. Book an appointment 2. Clinic timings …", but nothing handles a reply of "1". The patient follows the bot's own instruction and gets the same menu again.

**Prerequisites:** W2-01 (`t()`, `_conversation_lang`), W2-03.

**Repository Context:**
- `app/agent/templates/__init__.py::TEMPLATES["out_of_scope"]` — four languages; first sentence is the apology, followed by a numbered list after `"Here is what I can do:"` (or its translation).
- `app/agent/nodes/scope_gate.py` returns the `out_of_scope` template (a) for the `out_of_scope` intent and (b) together with `escalate: True` on consecutive low confidence. `output_gate.py` also substitutes it after a failed regeneration.
- `app/workers/inbound.py::process_event`: `_parse_message` yields `action_id` for list/button taps; action handlers (`_handle_cancel_action`, `_handle_booking_action`) run before the graph; the final reply is sent with `send_freeform`.
- `app/channels/whatsapp.py::send_slot_picker` is the pattern for a list message (window check → `_post` → audit).
- `app/agent/nodes/lang_detect.py::lang_detect(state)` sets `lang` from the text.
- The mock LLM classifies these English phrases as follows: "book appointment" → `book`; "clinic timings" → `faq_hours`; "clinic address" → `faq_location`; "appointment status" → `booking_status`; "talk to staff" → `human_request`.
- WhatsApp limits: list row title ≤ 24 characters, ≤ 10 rows, list button ≤ 20.

**Files to Inspect:** the files above; `app/agent/state.py`; `app/i18n/strings.py`; `tests/test_phase0_compliance.py` and any test asserting the `out_of_scope` text (`grep -rn "out_of_scope" tests`)

**Files to Modify/Create:**
- `app/channels/whatsapp.py` — `send_menu`.
- `app/workers/inbound.py` — menu tap mapping; send the menu after an out-of-scope reply.
- `app/agent/templates/__init__.py` — shorten `out_of_scope` to the apology sentence.
- `app/agent/state.py`, `app/agent/nodes/lang_detect.py` — `lang_override`.
- `app/i18n/strings.py` — menu strings.
- `tests/test_menu.py` — new.

**Detailed Implementation Instructions:**
1. **Strings** (four languages; add `hi`/`or` to `docs/i18n-review.md`): `menu.prompt` "Here is what I can help with:" · `menu.button` "Options" (≤ 20) · `menu.book` "Book appointment" · `menu.hours` "Clinic timings" · `menu.location` "Location" · `menu.status` "My appointment" · `menu.human` "Talk to staff" (row titles ≤ 24).
2. **`send_menu(tenant_id, wa_id, *, prompt, button_label, rows, operation_key)`** where `rows` is a list of `{"id", "title"}`; same structure as `send_slot_picker` (one section, no section title required — use the prompt's language-neutral empty string or omit the title key); audit `kind: "menu"`; raises `WindowClosedError` outside the window.
3. **Templates:** in each language of `out_of_scope`, keep only the apology sentence (remove "Here is what I can do:" and the numbered lines). Keep it specialty-neutral (W1-02 wording).
4. **Sending the menu (`inbound.py`):** after the final `send_freeform` of a bot reply, if `result.get("intent") == "out_of_scope"`, the conversation is still in `bot` state, and the reply was not an escalation, send `send_menu` with the five rows (`menu:book`, `menu:hours`, `menu:location`, `menu:status`, `menu:human`) in the conversation language, `operation_key=f"menu:{message_id or conversation_id}"`, and record it with `_record_flow_interactive(..., flow="menu", ...)`. A `WindowClosedError` here is logged and ignored.
5. **Handling taps:** define
```python
MENU_UTTERANCES = {
    "menu:book": "book appointment",
    "menu:hours": "clinic timings",
    "menu:location": "clinic address",
    "menu:status": "appointment status",
    "menu:human": "talk to staff",
}
```
   In `process_event`, after the human-state check and before the action handlers: if `action_id in MENU_UTTERANCES`, store the inbound tap (`_store_inbound(..., action_id=action_id)`), then continue down the normal path with `text = MENU_UTTERANCES[action_id]`, `action_id = ""`, and graph state `lang_override = <conversation language>`. Do **not** store the inbound a second time later in the function for this event, and do not update the stored conversation language from this synthetic text.
6. **`lang_override`:** add the optional key to `AgentState`; `lang_detect` returns `{"lang": state["lang_override"]}` when it is set and valid.
7. **Tests:** an unrecognised message yields the apology text followed by one list with the five ids, titles in the conversation language and within limits; tapping each row leads to the expected behaviour (book → slot picker; hours/location → FAQ answer or handoff when the KB lacks it; status → status reply; human → handoff acknowledgement and conversation state `human`); a Hindi conversation stays Hindi after a tap (reply strings are `hi`); no menu is sent when the reply escalated; an unknown `menu:xyz` id falls through without error; the inbound tap is stored exactly once.

**Interfaces & Data Contracts:** reply ids `menu:book`, `menu:hours`, `menu:location`, `menu:status`, `menu:human` (as fixed in `04-TARGET_ARCHITECTURE.md §4`, with `menu:status` replacing `menu:manage`). `AgentState.lang_override: str`.

**Edge Cases:** two consecutive out-of-scope messages → the second escalates (existing rule) and no menu is sent; patient types "1" → still out-of-scope, but now receives a tappable menu instead of an instruction it cannot follow; voice channel is unaffected (no menu, template still read aloud — now a single sentence).

**Non-Goals:** No menu on greeting. No change to scope-gate rules or escalation thresholds. No numeric-reply parsing. No changes to voice.

**Acceptance Criteria:** tests pass; `grep -n "1\. " app/agent/templates/__init__.py` prints nothing; golden transcripts (W2-08) still pass or are updated only where they expected the old numbered text; mock eval 25/25.

**Verification:**
```bash
uv run pytest -q tests/test_menu.py tests/test_golden_transcripts.py
uv run ruff check . && uv run mypy app && uv run pytest -q
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json
```

**Risk & Rollback:** Low–medium. Tests asserting the full old template text need their expected string shortened (allowed — the intent is unchanged). Rollback = revert.

**Effort & Complexity:** Small–medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** The compliance tests require the capability list to be part of the out-of-scope **text**; the mock LLM does not classify one of the five utterances as listed; `process_event` structure has changed so the synthetic-text approach would duplicate stored messages.

**Standalone Execution Prompt:**
```
Task W2-09 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet. Requires W2-01, W2-03.
1. i18n: add menu.prompt, menu.button, menu.book, menu.hours, menu.location, menu.status,
   menu.human in en/hi-Latn/hi/or (row titles <=24 chars, button <=20); add hi/or to
   docs/i18n-review.md.
2. whatsapp.py: add send_menu(tenant_id, wa_id, *, prompt, button_label, rows, operation_key),
   modelled on send_slot_picker, audit kind "menu".
3. templates: shorten every language of "out_of_scope" to its apology sentence (drop the numbered list).
4. inbound.py: after sending a bot reply whose intent is out_of_scope (not escalated, state still
   "bot"), send the menu with ids menu:book, menu:hours, menu:location, menu:status, menu:human in
   the conversation language and record it. On a tap of one of those ids: store the inbound once,
   then run the normal pipeline with text = MENU_UTTERANCES[id] (book appointment / clinic timings
   / clinic address / appointment status / talk to staff), action_id cleared, and
   lang_override = conversation language; never update the stored language from this text.
5. AgentState + lang_detect: support lang_override.
6. tests/test_menu.py per the packet.
Do NOT change scope_gate rules, voice, or add numeric-reply parsing.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q && the mock eval (25/25).
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
