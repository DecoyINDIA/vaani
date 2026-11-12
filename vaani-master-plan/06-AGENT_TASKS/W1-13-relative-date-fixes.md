### TASK ID: W1-13

**Title:** Date parser: whole-word matching, month names, and the `baje` AM/PM bug

**Priority:** P1

**Objective:** `resolve()` matches Latin-script keywords only as whole words, understands explicit dates with month names and "tarikh", and `parse_colloquial_time()` no longer turns "subah 10 baje" into 22:00.

**Why This Matters:** Keywords are matched with `k in phrase`, so "next month" hits `mon` (Monday), "satisfied" hits `sat`, "aajkal" hits `kal` (tomorrow). The patient is then shown slots for the wrong day. "15 November" is not understood at all and silently becomes today.

**Prerequisites:** None.

**Repository Context:**
- `app/booking/relative_date.py`:
  - `resolve(phrase, *, today, lang) -> date`: order is day-after-tomorrow keywords → tomorrow keywords → weekday names (incl. 3-letter abbreviations) → `DD/MM/YYYY` → `DD/MM` → `return today`.
  - `parse_colloquial_time(phrase) -> str | None`: `pm_indicators` contains `"baje"` and `"bajey"` ("o'clock", not PM); PM is applied before AM is considered.
  - `normalize_numerals` maps Devanagari/Odia digits to ASCII.
- `resolve` is called from `app/agent/nodes/tool_router.py`. `parse_colloquial_time` currently has no callers.
- Existing tests: `tests/test_relative_date_boundaries.py`.

**Files to Inspect:** `app/booking/relative_date.py`, `tests/test_relative_date_boundaries.py`

**Files to Modify/Create:** `app/booking/relative_date.py`; `tests/test_relative_date_table.py` (new).

**Detailed Implementation Instructions:**
1. Add a private helper and use it for **every** keyword check in `resolve`:
```python
def _has(phrase: str, keyword: str) -> bool:
    if keyword.isascii():
        return re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", phrase) is not None
    return keyword in phrase   # Devanagari / Odia: substring is correct
```
2. Add an explicit "today" check **first**: keywords `today`, `aaj`, `aj`, `आज`, `ଆଜି` → return `today`.
3. Keep the existing order for day-after-tomorrow, tomorrow, weekdays (now via `_has`).
4. After weekdays and before the numeric `DD/MM` patterns, add month-name parsing. Month table (ASCII, matched with `_has`): `jan|january, feb|february, mar|march, apr|april, may, jun|june, jul|july, aug|august, sep|sept|september, oct|october, nov|november, dec|december`. Accept `<day> <month>` and `<month> <day>` where day is `\d{1,2}` optionally followed by `st|nd|rd|th`. Year = `today.year`; if the resulting date is before `today`, use next year. Invalid dates (e.g. 31 Feb) fall through.
5. Add "tarikh" parsing: `(\d{1,2})\s*(?:tarikh|tareekh|tarik|तारीख|ତାରିଖ)` → that day in the current month if `>= today`, otherwise the same day next month (roll the year in December). Invalid day for the month falls through.
6. `parse_colloquial_time`: remove `"baje"` and `"bajey"` from `pm_indicators`. When both an AM word and a PM word are present, AM wins. Use `_has` for ASCII indicators here too (`am`, `pm` must not match inside other words).
7. Final fallback `return today` stays.
8. Table-driven tests with `today = date(2026, 11, 12)` (a Thursday):

| phrase | expected |
|---|---|
| `next month` | 2026-11-12 |
| `I am satisfied` | 2026-11-12 |
| `aajkal busy hoon` | 2026-11-12 |
| `kal` | 2026-11-13 |
| `kal subah` | 2026-11-13 |
| `parso` | 2026-11-14 |
| `day after tomorrow` | 2026-11-14 |
| `monday` | 2026-11-16 |
| `agle somvar` | 2026-11-16 |
| `thursday` | 2026-11-19 |
| `sat ko` | 2026-11-14 |
| `15 november` | 2026-11-15 |
| `nov 20th` | 2026-11-20 |
| `5 jan` | 2027-01-05 |
| `20 tarikh` | 2026-11-20 |
| `5 tarikh` | 2026-12-05 |
| `२० तारीख` | 2026-11-20 |
| `20/11` | 2026-11-20 |
| `aaj` | 2026-11-12 |
| `कल` | 2026-11-13 |
| `କାଲି` | 2026-11-13 |

`parse_colloquial_time`: `subah 10 baje` → `10:00`; `shaam 4 baje` → `16:00`; `4 baje` → `16:00`; `10 baje` → `10:00`; `dopahar 12` → `12:00`; `7:30 pm` → `19:30`; `namaste` → `None`.

**Interfaces & Data Contracts:** public signatures unchanged.

**Edge Cases:** the word `may` as a verb ("may I come tomorrow") — the month rule requires an adjacent day number, so it does not fire; `sun`/`sat`/`mon` now require word boundaries; mixed-script phrases.

**Non-Goals:** Do not call `parse_colloquial_time` from anywhere new. Do not change `format_colloquial_time`. Do not change the "unknown → today" fallback (W2-03 replaces it). No Hindi/Odia month names.

**Acceptance Criteria:** every table row passes; `tests/test_relative_date_boundaries.py` still passes; full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_relative_date_table.py tests/test_relative_date_boundaries.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Low — pure functions. Rollback = revert.

**Effort & Complexity:** Small effort, low-to-moderate reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** A table row conflicts with an assertion in the existing boundary test; report both and do not pick one.

**Standalone Execution Prompt:**
```
Task W1-13 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet (it contains the test
table). File: app/booking/relative_date.py only, plus a new tests/test_relative_date_table.py.
1. Add _has(phrase, keyword): ASCII keywords match only as whole words via
   (?<![a-z])keyword(?![a-z]); non-ASCII keywords keep substring matching. Use it for all keyword
   checks in resolve() and for the ASCII indicators in parse_colloquial_time().
2. resolve(): check today-words first (today, aaj, aj, आज, ଆଜି); keep the existing order; add
   month-name dates ("15 november", "nov 20th"; past dates roll to next year) and "<N> tarikh"
   (this month if not past, else next month) before the numeric DD/MM patterns; keep the final
   "return today".
3. parse_colloquial_time(): remove "baje"/"bajey" from pm_indicators; if both AM and PM words
   are present, AM wins.
4. Implement every row of the two tables in the packet as parametrized tests with
   today = date(2026, 11, 12).
Do NOT change signatures, format_colloquial_time, or any caller.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if a table row contradicts tests/test_relative_date_boundaries.py.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
