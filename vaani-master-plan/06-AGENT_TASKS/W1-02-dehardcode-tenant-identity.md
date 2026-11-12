### TASK ID: W1-02

**Title:** Remove the hardcoded clinic identity from prompts, templates and the output gate

**Priority:** P0

**Objective:** The agent introduces itself with the tenant's own name and uses specialty-neutral wording. No clinic name, city or specialty literal remains under `app/agent/` except inside the mock in `app/agent/llm.py`.

**Why This Matters:** The responder says "AI receptionist at Sharma Dental Clinic" for every tenant; templates say "dental clinic"/"dentist"; the output gate's location pattern contains `bhubaneswar`. A second clinic, or a non-dental one, would be misrepresented to its own patients.

**Prerequisites:** None.

**Repository Context:**
- `app/agent/nodes/responder.py:103` — system prompt begins `"You are an empathetic, professional AI receptionist at Sharma Dental Clinic.\n"`.
- `app/agent/nodes/intent.py:45,55,67` and few-shot example 4 (`'mujhe dr sharma se milna hai'`) — "dental clinic", "Dr. Sharma".
- `app/agent/templates/__init__.py` — `medical_refusal` (says dentist), `out_of_scope` (says dental clinic services), `location_landmark` (a full hardcoded address; **not referenced anywhere in code**).
- `app/agent/nodes/output_gate.py:48` — `r"\b(address|location|landmark|bhubaneswar)\b"`.
- Tenant document has `name`; there is no `business_type` field yet (treat as optional, default `"clinic"`).
- **Mock coupling (critical):** `app/agent/llm.py::get_mock_response` (a) classifies a call as intent-classification when the system prompt contains the word `intent` or `classify` — so the responder prompt must contain neither; (b) needs the literals `Grounded Facts:\n` and `\n\nStrict Citation Rule` in the responder prompt; (c) needs `User message: '…'` / `Patient latest message: '…'` in the user prompts. The mock's own answers mention "Sharma Dental Clinic"; leave them.

**Files to Inspect:** the four files above, `app/agent/llm.py` (read only), `app/models/collections.py` (`Tenants.find_by_id`), `tests/test_phase0_compliance.py`, `tests/test_output_grounding.py`, `evals/run_evals.py`

**Files to Modify/Create:**
- Create `app/agent/tenant_context.py`.
- Modify `responder.py`, `intent.py`, `templates/__init__.py`, `output_gate.py`, `app/agent/templates/README.md` (drop the `location_landmark` line).
- Create `tests/test_no_tenant_literals.py`.

**Detailed Implementation Instructions:**
1. `tenant_context.py`: `async def get_tenant_profile(tenant_id: str) -> dict[str, str]` returning `{"name": tenant.get("name") or "the clinic", "business_type": tenant.get("business_type") or "clinic"}`; on missing tenant or any exception return the defaults. Strip newlines from both values and cap each at 80 characters.
2. `responder.py`: call `get_tenant_profile(tenant_id)` once; first prompt line becomes `f"You are an empathetic, professional AI receptionist at {name}.\n"`. Change nothing else in the prompt.
3. `intent.py`: load the profile; replace "a dental clinic AI front-desk agent" with `f"a {business_type} AI front-desk agent"`; "not related to the dental clinic" → `f"not related to the {business_type}"`; `(e.g. 'Dr. Sharma')` → `(e.g. 'who is the doctor')`; few-shot 4 text → `'mujhe doctor se milna hai'`. `tenant_id` comes from `state.get("tenant_id") or ""`.
4. `templates/__init__.py`:
   - `medical_refusal`: en "our dentist" → "our doctor"; hi "हमारे दंत चिकित्सक" → "हमारे डॉक्टर"; hi-Latn "humare dentist" → "humare doctor"; or "ଆମ ଦନ୍ତ ଚିକିତ୍ସକଙ୍କ" → "ଆମ ଡାକ୍ତରଙ୍କ".
   - `out_of_scope`: en "dental clinic services" → "clinic services"; hi "दंत चिकित्सालय सेवाओं" → "क्लिनिक सेवाओं"; hi-Latn "dental clinic services" → "clinic services"; or "ଦନ୍ତ ଚିକିତ୍ସାଳୟ ସେବା" → "କ୍ଲିନିକ୍ ସେବା".
   - Delete the `location_landmark` entry.
5. `output_gate.py:48`: remove `|bhubaneswar` from the pattern.
6. `tests/test_no_tenant_literals.py`: walk `app/agent/**/*.py` excluding `llm.py`; fail if any file contains (case-insensitive) `sharma`, `dental`, `dentist`, `bhubaneswar`, `दंत`, `ଦନ୍ତ`.
7. Add one test that the responder system prompt contains the seeded tenant's name (capture the `system_prompt` passed to `query_llm` via monkeypatch) and contains neither `intent` nor `classify`.

**Interfaces & Data Contracts:** `get_tenant_profile(tenant_id) -> {"name": str, "business_type": str}`. Optional tenant field `business_type: str`.

**Edge Cases:** tenant not found → defaults; tenant name containing quotes/newlines → sanitized as in step 1; a tenant name that contains the word "intent" would break the mock → acceptable in tests only if no fixture does so (check fixtures; if one does, escalate).

**Non-Goals:** Do not edit `app/agent/llm.py`, `evals/`, the eval datasets, or `ops/seed_tenant.py`. Do not add `business_type` to onboarding. No localization work beyond the listed word swaps.

**Acceptance Criteria:** literal-scan test passes; mock eval still 25/25 (`uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json`); full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_no_tenant_literals.py
uv run ruff check . && uv run mypy app && uv run pytest -q
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json
```

**Risk & Rollback:** Medium — prompt edits can flip the mock's routing and fail many tests at once; that is the signal a marker was disturbed. Rollback = revert.

**Effort & Complexity:** Medium effort, moderate reasoning (mock coupling).

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** The mock eval drops below 25/25 after two attempts; a test asserts the exact old template wording for a reason other than the word swap; `location_landmark` turns out to be referenced.

**Standalone Execution Prompt:**
```
Task W1-02 in the Vaani repo. Read 07-AGENT_CONTEXT.md (especially "Mock-LLM coupling") and
this packet completely before editing.
Goal: no hardcoded clinic name/city/specialty under app/agent except in llm.py.
1. Create app/agent/tenant_context.py: get_tenant_profile(tenant_id) -> {"name","business_type"}
   from Tenants.find_by_id, defaults "the clinic"/"clinic", newlines stripped, max 80 chars.
2. responder.py line ~103: "...AI receptionist at {name}." Change nothing else; the prompt must
   keep "Grounded Facts:\n" and "\n\nStrict Citation Rule" and must not contain the words
   "intent" or "classify".
3. intent.py: replace "dental clinic" with {business_type}; remove "Dr. Sharma" examples as
   specified in the packet.
4. templates/__init__.py: apply the exact word swaps listed in the packet for medical_refusal
   and out_of_scope in en/hi/hi-Latn/or; delete the unused location_landmark template.
5. output_gate.py: remove "|bhubaneswar" from the location regex.
6. Add tests/test_no_tenant_literals.py (scan app/agent excluding llm.py for sharma, dental,
   dentist, bhubaneswar, दंत, ଦନ୍ତ) and a test that the responder system prompt contains the
   tenant name and neither "intent" nor "classify".
Do NOT edit app/agent/llm.py, evals/, or ops/.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q &&
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json  (must be 25/25)
Stop after two failed attempts at the eval and report.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
