### TASK ID: W2-01

> **Baseline note:** written against `847d5f5` with Wave 1 merged; locate code by symbol name. Wave 1 added the cancel flow (`cancel_flow`, `send_cancel_confirmation`), `UNSUPPORTED_REPLY`, and `app/booking/timefmt.py`.

**Title:** Localize every deterministic patient message; remember the conversation language

**Priority:** P1

**Objective:** All fixed patient-facing copy in the WhatsApp flows comes from one string table in four languages (`en`, `hi`, `hi-Latn`, `or`), chosen by a language stored on the conversation. Slot labels are rendered at send time in that language.

**Why This Matters:** Language is detected per message and thrown away. A patient who writes in Hindi gets an English slot picker, English buttons and an English confirmation. Vernacular service is the product's central claim.

**Prerequisites:** All of Wave 1 (chain A in particular).

**Repository Context:**
- `app/workers/inbound.py` holds the copy inline: stale selection, confirm prompt, re-pick prompt, booked / rescheduled, slot-taken (with and without alternatives), already confirmed, picker prompt, status found / not found, nothing to reschedule, cancel prompt / done / failed / kept, opt-out, opt-in, unsupported media.
- `app/channels/whatsapp.py` holds UI literals: list button "Choose a time", section title "Available appointments", buttons "Confirm", "Choose again", "Yes, cancel", "Keep appointment".
- `process_event` runs the graph only for free text; `result.get("lang")` is the detected language. Interactive taps and STOP/START never reach the graph.
- `booking_flow.slots` currently maps `slot_id → English label` built with `strftime("%a %d %b, %I:%M %p")` from the offset-aware ISO string that `slots_get` returns.
- Tenants have `locale_default`; contacts have no language field yet.
- WhatsApp limits: button title ≤ 20 chars, list button ≤ 20, section title ≤ 24, list row title ≤ 24, body ≤ 1024.
- Static safety templates in `app/agent/templates/__init__.py` are already four-language — leave them.

**Files to Inspect:** `app/workers/inbound.py`, `app/channels/whatsapp.py`, `app/booking/timefmt.py`, `app/agent/nodes/lang_detect.py`, `tests/test_handoff.py`, `tests/test_booking_journey.py`, `tests/test_two_clinic_whatsapp_acceptance.py`, `tests/test_cancel_confirmation.py`

**Files to Modify/Create:**
- `app/i18n/__init__.py` — `t()`, `LANGS`, `normalize_lang()`.
- `app/i18n/strings.py` — the table.
- `app/booking/timefmt.py` — `format_local` gains `lang`.
- `app/workers/inbound.py` — use `t()`; persist and read language; store slot instants.
- `app/channels/whatsapp.py` — UI labels become keyword parameters with the current English defaults.
- `docs/i18n-review.md` — list of strings needing native review.
- `tests/test_i18n.py` — new.

**Detailed Implementation Instructions:**
1. **`app/i18n`:** `LANGS = ("en", "hi", "hi-Latn", "or")`; `normalize_lang(value) -> str` (unknown → `"en"`); `t(key: str, lang: str, **params) -> str` looks up `STRINGS[key][lang]`, falls back to `en`, formats with `str.format(**params)`; unknown key raises `KeyError`.
2. **Keys and English text** (move the existing wording verbatim so English behaviour is unchanged):

| key | English | params |
|---|---|---|
| `booking.picker_prompt` | Choose a {service} time with {practitioner} on {date}. | service, practitioner, date |
| `booking.confirm_prompt` | Confirm {service} with {practitioner} on {when}? | service, practitioner, when |
| `booking.repick_prompt` | Please choose another appointment time. | |
| `booking.stale_selection` | That appointment is no longer in this selection. Please choose again. | |
| `booking.booked` | Your appointment is booked for {when}. | when |
| `booking.rescheduled` | Your appointment is rescheduled for {when}. | when |
| `booking.slot_taken_repick` | That slot was just taken. Please choose another appointment time. | |
| `booking.slot_taken_none` | That slot was just taken and no other offered time remains. Please ask for another date. | |
| `booking.already_confirmed` | Your appointment is already confirmed for {when}. | when |
| `status.found` | Your appointment is {status} for {when}. | status, when |
| `status.none` | I could not find an active appointment for this WhatsApp number. | |
| `reschedule.none` | I could not find an active appointment to reschedule. | |
| `cancel.prompt` | Cancel your appointment on {when}? | when |
| `cancel.done` | Your appointment on {when} has been cancelled. | when |
| `cancel.failed` | I could not cancel that appointment. Please contact the clinic. | |
| `cancel.kept` | Okay, your appointment is unchanged. | |
| `optout.done` | You have been unsubscribed from automated reminders. Reply START to opt back in. | |
| `optin.done` | You have re-subscribed to appointment reminders. How can I help you today? | |
| `media.unsupported` | Sorry, I can only read text messages right now. Please type your question and I will help. | |
| `ui.choose_time` | Choose a time | ≤ 20 |
| `ui.slots_title` | Available appointments | ≤ 24 |
| `ui.confirm` | Confirm | ≤ 20 |
| `ui.choose_again` | Choose again | ≤ 20 |
| `ui.cancel_yes` | Yes, cancel | ≤ 20 |
| `ui.cancel_keep` | Keep appointment | ≤ 20 |
| `status.word.confirmed` / `status.word.rescheduled` | confirmed / rescheduled | |

   If the English wording on your base branch differs from this table, keep the wording in the code and note the difference.
3. **Translations:** write `hi-Latn` (natural Hinglish, respectful "aap"), `hi` (Devanagari, "आप") and `or` (Odia script, "ଆପଣ") for every key. Keep STOP/START as Latin keywords inside all languages. List every `hi` and `or` string in `docs/i18n-review.md` under "Needs native-speaker review" — a human signs them off before the pilot.
4. **Date/time:** `format_local(instant, tz, lang="en")`. `en` and `hi-Latn`: unchanged format. `hi`: weekday/month abbreviations सोम मंगल बुध गुरु शुक्र शनि रवि / जन फ़र मार्च अप्रैल मई जून जुल अग सित अक्टू नव दिस, e.g. `गुरु 12 नव, 10:00 AM`. `or`: Odia weekday abbreviations (draft, add to the review list) with a numeric date, e.g. `<weekday> 12/11, 10:00 AM`. Every result must be ≤ 24 characters (it is used as a list row title) — assert this in a test over all weekdays and months.
5. **Language memory in `inbound.py`:**
   - Add `async def _conversation_lang(tenant_id, conversation_db_id, contact_id) -> str`: conversation `lang` → contact `lang_pref` → tenant `locale_default` → `"en"`, normalized.
   - After the graph returns, compute `detected = normalize_lang(result.get("lang"))`. Persist it to `conversations.lang` and `contacts.lang_pref` **only if** the text contains non-Latin script **or** has at least three words (so "ok" or "yes" cannot flip a Hindi conversation to English). Use the persisted/known language for the reply strings.
   - Interactive taps, STOP/START and unsupported-media replies use `_conversation_lang(...)`.
6. **Slot instants:** store `booking_flow.slots` as `slot_id → ISO-8601 string with offset` (the value from `slots_get`). Render labels with `format_local(datetime.fromisoformat(value), tz, lang)` whenever a picker or a confirmation is sent. Reader compatibility: if a stored value does not parse as ISO, use it as the label unchanged.
7. **`whatsapp.py`:** add keyword-only parameters with the present English literals as defaults — `send_slot_picker(..., button_label="Choose a time", section_title="Available appointments")`, `send_booking_confirmation(..., confirm_title="Confirm", again_title="Choose again")`, `send_cancel_confirmation(..., yes_title="Yes, cancel", keep_title="Keep appointment")` — truncating each to its WhatsApp limit. `inbound.py` passes `t("ui.…", lang)`.
8. **Tests:** every key has all four languages and every `{param}` in English appears in each translation; UI strings respect their length limits in all languages; a Hindi-script "book" message produces a picker whose button label and prompt are the `hi` strings and the following confirmation text is `hi`; a tap after a Hindi conversation stays Hindi; "ok" does not change a stored `hi`; legacy English-label `slots` values still render.

**Interfaces & Data Contracts:** `conversations.lang`, `contacts.lang_pref` ∈ `LANGS`. `booking_flow.slots: {slot_id: ISO string}`. `t(key, lang, **params) -> str`.

**Edge Cases:** missing translation → English; a tenant with `locale_default` outside `LANGS` → `en`; a mid-flow language switch applies from the next message.

**Non-Goals:** No changes to the safety templates, the LLM prompts, reminder/alert templates (Meta-approved, separate), the dashboard, or voice. No new languages.

**Acceptance Criteria:** `grep -nE '"(Your appointment|Please choose|That slot|Choose a|Confirm |I could not|You have|Sorry, I can|Cancel your|Okay, your)' app/workers/inbound.py` prints nothing; tests pass; existing English-flow tests pass without assertion changes (English wording is preserved).

**Verification:**
```bash
uv run pytest -q tests/test_i18n.py tests/test_handoff.py tests/test_booking_journey.py tests/test_cancel_confirmation.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Medium. Translation quality cannot be verified by tests — hence the review file. The `slots` storage change touches the booking state machine; the legacy-label fallback covers in-flight conversations. Rollback = revert (stored ISO values then show as raw labels until the flow expires; acceptable pre-pilot).

**Effort & Complexity:** Medium–large effort, moderate reasoning, high language care.

**Recommended Agent Tier:** Medium-capability agent with strong Hindi/Odia; mandatory human native review of `docs/i18n-review.md`.

**Escalation Conditions:** A Hindi or Odia UI string cannot fit its length limit without becoming unnatural (list it, use the best short form); existing tests assert stored English labels in `booking_flow.slots`; you are not confident in the Odia — deliver Odia marked "machine draft" rather than omit the review entry.

**Standalone Execution Prompt:**
```
Task W2-01 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this entire packet (it contains the
key table). Wave 1 must be merged.
1. Create app/i18n (LANGS, normalize_lang, t(key, lang, **params) with English fallback) and
   app/i18n/strings.py containing every key in the packet table in en, hi-Latn, hi, or. English
   text = the wording currently in app/workers/inbound.py and app/channels/whatsapp.py, verbatim.
2. Extend app/booking/timefmt.format_local with lang (rules in the packet; every label <=24 chars).
3. app/workers/inbound.py: replace all inline patient copy with t(...); add _conversation_lang()
   (conversation.lang -> contact.lang_pref -> tenant.locale_default -> "en"); after the graph,
   persist the detected language to conversations.lang and contacts.lang_pref only when the text
   has non-Latin script or >=3 words; store booking_flow.slots as slot_id -> ISO string and render
   labels at send time (non-ISO legacy values are used as-is).
4. app/channels/whatsapp.py: turn the UI literals into keyword-only parameters with the same
   English defaults; inbound passes t("ui...", lang).
5. Write docs/i18n-review.md listing every hi and or string for native review.
6. Add tests/test_i18n.py per the packet.
Do NOT touch app/agent/templates, prompts, reminders, voice, or the dashboard.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
