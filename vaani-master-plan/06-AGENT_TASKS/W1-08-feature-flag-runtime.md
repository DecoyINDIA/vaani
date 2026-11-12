### TASK ID: W1-08

**Title:** Feature-flagged runtime validation so a WhatsApp-only deployment can start

**Priority:** P1

**Objective:** Staging/production startup requires voice, payment and billing credentials only when the matching feature flag is on. With all three flags off, the app boots with WhatsApp + LLM + datastore settings alone, and the voice/payment webhooks are not mounted.

**Why This Matters:** `Settings.validate_runtime()` currently demands Exotel, Sarvam, Razorpay keys and a GSTIN in every non-dev environment. The recommended WhatsApp-only pilot cannot boot without inventing dummy secrets — which defeats the guard.

**Prerequisites:** None. (Optional input: discovery DISC-01.)

**Repository Context:**
- `app/config.py`: `validate_runtime()` returns early in `dev`; otherwise checks `jwt_secret`, rejects mock flags, requires a tuple of 19 settings, then STT/TTS provider keys.
- `app/main.py`: unconditionally includes `meta`, `razorpay`, `exotel` routers. `app/workers/inbound.py::run` also calls `settings.validate_runtime()`.
- `.env.example`: `JWT_SECRET=changeme` (a value the guard rejects) and `INVOICE_SAC_CODE=998314` while the code default is `998313`.
- Tests that exercise the guard: `tests/test_fixed_findings.py`, `tests/test_production_load_security_closure.py`.

**Files to Inspect:** `app/config.py`, `app/main.py`, `.env.example`, the two test files; `grep -rn "bsp_access_token\|bsp_waba_id\|bsp_phone_number_id" app`

**Files to Modify/Create:** `app/config.py`, `app/main.py`, `.env.example`, `tests/test_feature_flags.py` (new), the two existing test files (add flags where they expect voice/payment requirements).

**Detailed Implementation Instructions:**
1. Add settings (default `False`): `enable_voice`, `enable_payments`, `enable_billing`.
2. Restructure the required list in `validate_runtime()`:
   - **Always:** `meta_app_secret`, `meta_webhook_verify_token`, `openrouter_api_key`, `llm_model_classifier`, `llm_model_responder`, `llm_model_embedding`.
   - **`bsp_access_token`, `bsp_waba_id`, `bsp_phone_number_id`:** run the grep above. If they are read nowhere outside `app/config.py`, remove them from the required list (keep the fields) and state this in your report. If they are read elsewhere, keep them required.
   - **If `enable_voice`:** `exotel_sid`, `exotel_api_key`, `exotel_api_token`, `exotel_subdomain`, plus the existing STT/TTS provider-key checks (move those checks inside this condition).
   - **If `enable_payments` or `enable_billing`:** `razorpay_key_id`, `razorpay_key_secret`, `razorpay_webhook_secret`.
   - **If `enable_billing`:** `razorpay_plan_starter_id`, `razorpay_plan_pro_id`, `xolver_gstin`.
   - JWT-secret, mock-flag and embedding-dimension checks stay unconditional.
3. `app/main.py`: always include the Meta router; include the Exotel router only when `settings.enable_voice`; include the Razorpay router only when `settings.enable_payments or settings.enable_billing`.
4. `.env.example`: add `ENABLE_VOICE=false`, `ENABLE_PAYMENTS=false`, `ENABLE_BILLING=false` under `# --- App ---` with a one-line comment each; change `JWT_SECRET=changeme` to `JWT_SECRET=` followed by the comment `# required outside dev: 32+ random characters`; change `INVOICE_SAC_CODE` to `998313`.
5. Tests (`tests/test_feature_flags.py`, constructing `Settings(...)` directly): staging with flags off and only the always-required values → `validate_runtime()` passes; `enable_voice=True` without Exotel values → raises and the message names the missing settings; `enable_billing=True` without GSTIN → raises; `enable_payments=True` with Razorpay key/secret/webhook secret → passes; default JWT secret still rejected with all flags off.
6. In the two existing test files, where a test expects a voice/payment/billing setting to be required, set the corresponding flag to `True` in that test's settings so the **same assertion** still holds. Do not delete or loosen assertions.
7. If existing tests call voice or Razorpay routes through the app created at import time, make those tests enable the flag (via the env var before app creation, following how `tests/conftest.py` sets `USE_MOCK_ADAPTERS`). Prefer setting `ENABLE_VOICE`/`ENABLE_PAYMENTS`/`ENABLE_BILLING` to `true` in `tests/conftest.py` with `os.environ.setdefault` so the existing suite keeps exercising those routes.

**Interfaces & Data Contracts:** new env vars `ENABLE_VOICE`, `ENABLE_PAYMENTS`, `ENABLE_BILLING` (booleans). Error message format unchanged: `"Unsafe runtime configuration: …"`.

**Edge Cases:** dev environment still skips validation entirely; flags on in dev with missing credentials → no error (unchanged dev behaviour).

**Non-Goals:** No per-tenant feature flags. No change to the scheduler in `inbound.py` (the monthly-invoice job still runs; see DISC-02). No edits to gateway, voice or billing modules. No CI workflow edits.

**Acceptance Criteria:** new tests pass; existing guard tests keep their assertions; with flags off, `create_app()` exposes no `/webhooks/exotel*` or `/webhooks/razorpay` route (assert via `app.routes` in a test using a fresh `create_app()` with patched settings).

**Verification:**
```bash
uv run pytest -q tests/test_feature_flags.py tests/test_fixed_findings.py tests/test_production_load_security_closure.py
uv run ruff check . && uv run mypy app && uv run pytest -q
```

**Risk & Rollback:** Medium — this touches the fail-closed guard. The always-on checks (JWT secret, no mocks) must remain unconditional. Rollback = revert.

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** Keeping an existing security assertion would require more than adding a flag; `settings` is consumed at import time in a way that prevents conditional router mounting in tests; the `bsp_*` settings are read outside config in a way you cannot classify.

**Standalone Execution Prompt:**
```
Task W1-08 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet fully.
Goal: staging/prod must boot for a WhatsApp-only deployment.
1. app/config.py: add enable_voice, enable_payments, enable_billing (bool, default False).
   In validate_runtime(): always require meta_app_secret, meta_webhook_verify_token,
   openrouter_api_key, llm_model_classifier, llm_model_responder, llm_model_embedding;
   require exotel_* and the STT/TTS provider keys only if enable_voice; razorpay_key_id/
   key_secret/webhook_secret if enable_payments or enable_billing; razorpay_plan_*_id and
   xolver_gstin only if enable_billing. Keep the JWT-secret, mock-flag and embedding-dimension
   checks unconditional. For bsp_access_token/bsp_waba_id/bsp_phone_number_id: grep app/; if they
   are unused outside config.py drop them from the required list and report it, else keep them.
2. app/main.py: mount the Exotel router only if enable_voice; the Razorpay router only if
   enable_payments or enable_billing.
3. .env.example: add the three flags; JWT_SECRET= with a comment; INVOICE_SAC_CODE=998313.
4. tests/conftest.py: os.environ.setdefault the three flags to "true" so the existing suite still
   exercises those routes. Add tests/test_feature_flags.py per the packet. In
   tests/test_fixed_findings.py and tests/test_production_load_security_closure.py add the flag
   where a test expects those settings to be required - never loosen an assertion.
Do NOT edit gateway/voice/billing modules, inbound.py, or CI workflows.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if a security assertion cannot be preserved by adding a flag.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
