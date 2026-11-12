### TASK ID: W1-11

**Title:** Owner API view models: patient names, phone, appointment time, doctor

**Priority:** P1

**Objective:** `GET /api/conversations` and `GET /api/bookings` return, in addition to today's fields, the joined data a receptionist needs: who the patient is, when the appointment is, with which doctor.

**Why This Matters:** Both routes return raw Mongo documents. A booking has only `slot_id` and `contact_id`, so the dashboard can show neither a name nor a time. Staff cannot run a front desk from it.

**Prerequisites:** W1-07 (same file). Owner decision D4 (staff may see patient name and phone) is assumed **yes**.

**Repository Context:**
- `app/owner_api/routes.py::list_conversations` (≈ 40-54) and `list_bookings` (≈ 215-229): paginated `find({})`, `serialize_mongo(results)`.
- `conversations.contact_id` is usually the **string** form of the contact's ObjectId; `bookings.contact_id` and `bookings.slot_id` may be ObjectId or string. Always match with `mongo_id_candidates(str(value))`.
- `slots`: `{practitioner_id (string), start, end}` naive UTC. `practitioners`: `{_id (string slug), name}`. `contacts`: `{name, wa_id, phone?}`.
- `messages`: `{conversation_id (string), direction, text, ts}`. `escalations`: `{conversation_id, status: "open"|"resolved"}`.
- `conversations.last_msg_at` is set from W1-10 onward; older rows may lack it.
- `app/booking/timefmt.py::tenant_timezone` exists after W1-05; if it is not on your base branch, inline `ZoneInfo(tenant.get("timezone", "Asia/Kolkata"))`.

**Files to Inspect:** `app/owner_api/routes.py`, `app/models/base.py`, `app/models/collections.py`, `tests/test_owner_route_authorization.py`, `tests/test_browser_owner_acceptance.py`

**Files to Modify/Create:** `app/owner_api/views.py` (new — enrichment helpers); `app/owner_api/routes.py` (two list routes call the helpers); `tests/test_owner_view_models.py` (new).

**Detailed Implementation Instructions:**
1. Create `app/owner_api/views.py` with two async helpers (signatures below). Use **batched** lookups: collect ids from the page, run one `find({"_id": {"$in": [...]}})` per collection, build dicts keyed by `str(_id)`. No per-row queries except the last-message preview (one `find_one` per conversation, sorted `ts` desc — acceptable for ≤ 200 rows).
2. `enrich_conversations` adds to each (already serialized) conversation:
   - `contact`: `{"id", "name", "phone"}` where phone = `wa_id` or `phone`; `None` when the contact is missing.
   - `last_message_preview`: latest message `text` truncated to 80 characters, `""` if none.
   - `last_msg_at`: keep the stored value; if absent use the latest message `ts`; ISO-8601 with tenant offset.
   - `open_escalation`: `True` if an escalation with `status == "open"` exists for the conversation id.
3. `enrich_bookings` adds to each booking:
   - `contact`: as above.
   - `start`, `end`: slot instants as ISO-8601 **with the tenant UTC offset** (e.g. `2026-11-12T10:00:00+05:30`); `None` if the slot is missing.
   - `practitioner`: `{"id", "name"}` or `None`.
4. In the two routes: keep the existing query, sort and pagination; after `serialize_mongo`, pass the list through the helper and return it. Existing keys (including `_id`) must remain.
5. Tests with two tenants: names/phones/start/practitioner appear for tenant A; a contact, slot or practitioner belonging to tenant B with a colliding id is never joined into tenant A's response; missing slot → `start is None`; conversation without messages → preview `""`.

**Interfaces & Data Contracts:**
```python
async def enrich_conversations(tenant_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]
async def enrich_bookings(tenant_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]
```
All added datetimes are strings; all added ids are strings. Additive only — no key removed or renamed.

**Edge Cases:** mixed ObjectId/string ids on the same page; contact erased (missing) → `contact: None`; empty page → return `[]` without querying.

**Non-Goals:** No new routes, filters or sorting. No dashboard changes (W1-12). No denormalization writes. No changes to `/deliveries` or `/processing` (they stay PII-free).

**Acceptance Criteria:** new tests pass; tenant-isolation grep prints nothing; full suite green; response time for a 50-row page uses ≤ 5 batched queries plus the per-conversation preview lookups.

**Verification:**
```bash
uv run pytest -q tests/test_owner_view_models.py tests/test_owner_route_authorization.py
uv run ruff check . && uv run mypy app && uv run pytest -q
grep -rnE 'db\[[^]]+\]\.(find|insert|update|delete)' app --include='*.py' | grep -v '^app/models/'
```

**Risk & Rollback:** Medium — id-type mismatches can silently yield `None` joins; the tests must cover both id forms. Rollback = revert (additive change).

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** An existing test asserts that conversation or booking list responses must **not** contain patient name or phone (that contradicts decision D4 — stop). The accessor base lacks a way to query `_id $in` within tenant scope.

**Standalone Execution Prompt:**
```
Task W1-11 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet. Base on W1-07.
Create app/owner_api/views.py with
  enrich_conversations(tenant_id, rows) and enrich_bookings(tenant_id, rows)
and call them at the end of list_conversations and list_bookings in app/owner_api/routes.py
(after serialize_mongo; keep query/sort/pagination and all existing keys).
Conversations gain: contact {id,name,phone}, last_message_preview (<=80 chars),
last_msg_at (stored value or latest message ts, ISO with tenant offset), open_escalation (bool).
Bookings gain: contact {id,name,phone}, start/end (slot instants, ISO with tenant offset),
practitioner {id,name}. Missing joins -> None.
Rules: tenant-scoped accessors only; match ids with mongo_id_candidates(str(id)); batch lookups
with $in; slots are naive UTC -> convert with the tenant timezone (default Asia/Kolkata).
Add tests/test_owner_view_models.py incl. a cross-tenant negative and both id forms.
Do NOT touch the dashboard, other routes, or /deliveries and /processing.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q, plus the tenant-isolation grep.
Stop and report if an existing test requires these lists to exclude patient name/phone.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
