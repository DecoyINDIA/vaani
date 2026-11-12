### TASK ID: W1-07

**Title:** Allow-list the fields returned by `GET /api/settings`

**Priority:** P1

**Objective:** The settings endpoint returns only an explicit set of clinic-facing fields; internal configuration never reaches the browser.

**Why This Matters:** The route returns the whole tenant document to any staff member, including `whatsapp.access_token_env` (the name of the secret), `whatsapp.phone_number_id`, GSTIN and any billing/provider fields added later.

**Prerequisites:** W1-06 (same file; rebase).

**Repository Context:**
- `app/owner_api/routes.py::get_settings_api` (≈ 440-445): `return serialize_mongo(tenant)`.
- `PUT /api/settings` accepts `name`, `landmark_line`, `location_pin` (owner only) — unchanged.
- The dashboard Settings tab reads the object returned here (`data.settings[0]`).
- Tenant fields (from `ops/tenant-config.example.json`): `name, timezone, plan, locale_default, wa_number, voice_number, landmark_line, location_pin, dashboard_url, gstin, whatsapp{…}, business_hours[], holiday_calendar[]`.

**Files to Inspect:** `app/owner_api/routes.py`, `dashboard/src/App.tsx` (Settings component — which keys it reads), `tests/test_owner_route_authorization.py`, `tests/test_browser_owner_acceptance.py`

**Files to Modify/Create:** `app/owner_api/routes.py`; `tests/test_settings_allow_list.py` (new).

**Detailed Implementation Instructions:**
1. Add a module constant:
   `SETTINGS_FIELDS = ("_id", "name", "timezone", "plan", "locale_default", "wa_number", "voice_number", "landmark_line", "location_pin", "business_hours", "holiday_calendar")`
2. In `get_settings_api`, build `{k: tenant[k] for k in SETTINGS_FIELDS if k in tenant}` and return it through `serialize_mongo`.
3. Confirm every key the dashboard Settings component reads is in the list; if it reads another non-sensitive key, add that key and say so in your report.
4. Test: seed a tenant containing `whatsapp`, `gstin`, `razorpay_account_id` and an arbitrary extra key; assert the response keys are a subset of `SETTINGS_FIELDS` and that `whatsapp`, `gstin`, `razorpay_account_id` are absent; assert `name` is present.

**Interfaces & Data Contracts:** response is a flat object whose keys ⊆ `SETTINGS_FIELDS`. 404 behaviour unchanged.

**Edge Cases:** tenant missing optional keys → those keys are simply absent.

**Non-Goals:** No change to `PUT /api/settings`. No new editable fields. No role change (staff may still read).

**Acceptance Criteria:** new test passes; existing tests pass (update any assertion that expected a removed key only if that key is sensitive — otherwise escalate).

**Verification:**
```bash
uv run pytest -q tests/test_settings_allow_list.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Low. Rollback = revert.

**Effort & Complexity:** Small, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** The dashboard or an existing test depends on a tenant field that looks sensitive (`whatsapp`, `gstin`, anything containing `token`, `secret`, `key`, `account`).

**Standalone Execution Prompt:**
```
Task W1-07 in the Vaani repo. Read 07-AGENT_CONTEXT.md first. Base on W1-06.
app/owner_api/routes.py get_settings_api returns the entire tenant document. Change it to
return only these keys when present: _id, name, timezone, plan, locale_default, wa_number,
voice_number, landmark_line, location_pin, business_hours, holiday_calendar
(module constant SETTINGS_FIELDS), still via serialize_mongo.
Check which keys the Settings component in dashboard/src/App.tsx reads; if a non-sensitive one
is missing from the list add it and report it.
Add tests/test_settings_allow_list.py: tenant seeded with whatsapp, gstin, razorpay_account_id
-> none of them in the response; name present; keys subset of SETTINGS_FIELDS.
Do NOT change PUT /api/settings or roles.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if anything depends on a sensitive field.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
