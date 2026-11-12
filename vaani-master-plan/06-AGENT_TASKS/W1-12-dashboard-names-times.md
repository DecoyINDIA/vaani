### TASK ID: W1-12

**Title:** Dashboard shows patient names, real timestamps and appointment date/time

**Priority:** P1

**Objective:** The Inbox and Appointments tabs display the fields added by W1-11 so a receptionist can see who wrote, when, and who is coming at what time.

**Why This Matters:** Inbox rows read "Conversation a1b2c3" with the literal word `now` as the time; the appointments table shows an 8-character "patient reference" and no date. The screen is not usable for its purpose.

**Prerequisites:** W1-11 merged (API fields), W1-06 (same file).

**Repository Context:**
- Whole SPA: `dashboard/src/App.tsx` (very long lines; edit surgically). Styles: `dashboard/src/index.css`.
- `type Item = Record<string, unknown> & { _id: string }`.
- `Inbox` component: list buttons render `Conversation {item._id.slice(-6)}`, `{channel} · {state}`, `<time>now</time>`; thread header renders `…{selected._id.slice(-8)}`.
- `Bookings` component: table columns `Patient reference | Service | Status | Source | (action)`.
- API fields now available — conversations: `contact {id,name,phone} | null`, `last_message_preview`, `last_msg_at` (ISO), `open_escalation`; bookings: `contact`, `start` (ISO with offset) `| null`, `practitioner {id,name} | null`.
- No new npm dependencies.

**Files to Inspect:** `dashboard/src/App.tsx`, `dashboard/src/index.css`

**Files to Modify/Create:** `dashboard/src/App.tsx`; `dashboard/src/index.css` only if a new class is needed.

**Detailed Implementation Instructions:**
1. Add three pure helpers near the top of `App.tsx`:
   - `contactLabel(item: Item): string` → `contact.name` if non-empty and not equal to the phone; else `contact.phone`; else `` `Conversation ${item._id.slice(-6)}` ``.
   - `timeAgo(iso: unknown): string` → `"just now"` (< 1 min), `"N min ago"`, `"N h ago"`, `"N d ago"`; `""` for missing/invalid input.
   - `formatWhen(iso: unknown): string` → `new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(new Date(iso))`; `"—"` for missing/invalid.
2. **Inbox list row:** title = `contactLabel(item)`; second line = `last_message_preview` when present, else the existing `{channel} · {state}`; replace `<time>now</time>` with `<time>{timeAgo(item.last_msg_at)}</time>`; when `open_escalation` is true add a small text badge "Needs staff".
3. **Thread header:** heading = `contactLabel(selected)`; under it show the phone (if different from the label).
4. **Appointments table:** columns become `Patient | Date & time | Doctor | Service | Status | (action)`. Patient cell = name with phone on a second line; Date & time = `formatWhen(item.start)`; Doctor = `practitioner.name` or "—". Remove the `Source` column.
5. Read nested fields defensively (values are `unknown`): write a tiny `obj(value): Record<string, unknown>` helper returning `{}` for non-objects.
6. Keep every existing action (takeover, reply, return, cancel, load more) working unchanged.

**Interfaces & Data Contracts:** consumes the W1-11 response shapes only; sends nothing new.

**Edge Cases:** `contact` null (erased) → fallback label; `start` null → "—"; name equal to phone (first-contact default) → show phone once.

**Non-Goals:** No new tabs, filters, sorting or calendar. No refactor into multiple files (W3-09). No styling overhaul. No changes to auth or `api()`.

**Acceptance Criteria:**
- `grep -n ">now<" dashboard/src/App.tsx` prints nothing.
- `grep -n "Patient reference" dashboard/src/App.tsx` prints nothing.
- `npm run lint` and `npm run build` succeed.
- Manual check against a mock-adapter API: inbox shows a name and a relative time; appointments show date/time and doctor.

**Verification:**
```bash
cd dashboard && npm ci && npm run lint && npm run build
```
```bash
uv run pytest -q tests/test_browser_owner_acceptance.py
```

**Risk & Rollback:** Low — presentation only. Rollback = revert.

**Effort & Complexity:** Medium effort (dense file), low reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** The API does not return the W1-11 fields on your base branch; a CI/browser test asserts the old column headings or the string "Conversation " and cannot be updated without changing its intent.

**Standalone Execution Prompt:**
```
Task W1-12 in the Vaani repo. Read 07-AGENT_CONTEXT.md first. Requires W1-11 merged.
Edit dashboard/src/App.tsx only (index.css if a class is needed). No new dependencies.
Add helpers contactLabel(item), timeAgo(iso), formatWhen(iso) (Intl.DateTimeFormat "en-IN",
weekday short, day numeric, month short, hour numeric, minute 2-digit) and obj(value).
Inbox row: title = contact name (fallback phone, fallback "Conversation <last6>"); second line =
last_message_preview or the existing channel·state; replace the literal <time>now</time> with
timeAgo(item.last_msg_at); show a "Needs staff" badge when open_escalation is true.
Thread header: contact label + phone.
Appointments table columns: Patient (name + phone) | Date & time (formatWhen(item.start)) |
Doctor (practitioner.name) | Service | Status | action. Remove "Source" and "Patient reference".
Handle null contact/start/practitioner. Keep all existing actions working.
Do NOT restructure the file, add tabs, or touch api()/auth.
Run: cd dashboard && npm ci && npm run lint && npm run build ; then
grep -n ">now<\|Patient reference" dashboard/src/App.tsx   (must print nothing).
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
