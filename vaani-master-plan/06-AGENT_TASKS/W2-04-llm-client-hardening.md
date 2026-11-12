### TASK ID: W2-04

> **Baseline note (applies to every Wave 2 packet):** written against commit `847d5f5` with Wave 1 assumed merged. Line numbers are approximate — locate code by symbol name. If a Wave 1 symbol named here (`strip_citations`, `format_local`, `get_tenant_profile`, `cancel_flow`, `ENABLE_*`) is missing on your base branch, stop and report.

**Title:** Harden the LLM client: shared connection, 8 s timeout, retry/fallback, JSON mode, call telemetry

**Priority:** P1

**Objective:** `query_llm` uses one shared HTTP client, fails fast, retries once (on the fallback model when configured), can request JSON output, and records latency and token usage for every real call. A public `call_openrouter` function exposes the real path for the eval harness.

**Why This Matters:** Today each call opens a new connection, waits up to 30 s, falls back only on a non-200 status (never on a timeout), and parses the classifier's free text — any stray token is treated as an outage and hands the patient to staff. Nothing records cost or latency, so COGS and the reply-time goal cannot be measured.

**Prerequisites:** Wave 1 merged. First task of Wave 2.

**Repository Context:**
- `app/agent/llm.py`: `get_mock_response(prompt, model)` (rule-based, used by all tests — do not change) and `query_llm(prompt, model, system_prompt=None, temperature=0.0, max_tokens=500)`. Mock path is taken when `settings.use_mock_adapters or settings.use_mock_llm`. Real path posts to `https://openrouter.ai/api/v1/chat/completions`.
- Callers: `app/agent/nodes/intent.py` (`temperature=0.0`) and `app/agent/nodes/responder.py` (`temperature=0.2`). Tests call `query_llm` directly in `tests/test_fixed_findings.py` (≈ lines 100-126).
- Accessors live in `app/models/collections.py`; indexes in `ensure_indexes()`.
- Message work leases last 60 s (`Messages.acquire_work_unscoped`), so one inbound event must finish well inside that.

**Files to Inspect:** `app/agent/llm.py`, `app/agent/nodes/intent.py`, `app/agent/nodes/responder.py`, `app/models/collections.py` (pattern of a simple accessor + its index), `app/config.py`, `tests/test_fixed_findings.py`

**Files to Modify/Create:**
- `app/agent/llm.py` — client, retry, JSON mode, telemetry hook.
- `app/config.py` — `llm_timeout_seconds: float = 8.0`, `llm_json_mode: bool = True`.
- `app/models/collections.py` — `class LlmCalls(TenantScoped)` (`collection = "llm_calls"`), indexes.
- `app/agent/nodes/intent.py`, `responder.py` — pass `tenant_id`, `node`, and (`intent` only) `json_mode=True`.
- `.env.example` — the two new settings.
- `tests/test_llm_client.py` — new.

**Detailed Implementation Instructions:**
1. Module-level lazy client: `_http: httpx.AsyncClient | None`; `_client()` creates `httpx.AsyncClient(timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=3.0))` once. Add `set_http_client(client | None)` for tests.
2. Add the public coroutine (signature below) that performs **one** HTTP attempt and returns `(text, usage)`; raise `LlmError(retryable: bool)` — retryable for `httpx.TimeoutException`, `httpx.TransportError`, HTTP 429 and ≥ 500; not retryable for other 4xx or a malformed body.
3. `query_llm`: keep the mock branch and the missing-key check exactly as they are. Real path: attempt 1 on `model`; on a retryable error attempt 2 on `settings.llm_model_fallback_provider or model`; then raise `RuntimeError`. Non-retryable → raise at once. When `json_mode and settings.llm_json_mode`, send `"response_format": {"type": "json_object"}`.
4. Telemetry: after each real attempt (success or failure) call `_record_call(...)`, which inserts into `LlmCalls(tenant_id)` when `tenant_id` is non-empty. Wrap the insert in `try/except Exception` — telemetry must never fail a call. Never record prompt or completion text.
5. `ensure_indexes()`: `llm_calls` index on `(tenant_id, ts)` and a TTL index on `ts` of 30 days.
6. Nodes: `intent.py` passes `json_mode=True, node="intent", tenant_id=state.get("tenant_id") or ""`; `responder.py` passes `node="responder", tenant_id=tenant_id`. Keep the existing code-fence cleanup in `intent.py`.
7. Tests (inject `httpx.MockTransport` via `set_http_client`; monkeypatch `settings` to real-LLM mode the way `tests/test_fixed_findings.py` does; monkeypatch `app.agent.llm._record_call` to capture calls): success returns text and records one call with token counts; timeout then success → two attempts, second on the fallback model; HTTP 400 → one attempt, raises; HTTP 500 twice → raises `RuntimeError`; `json_mode=True` puts `response_format` in the request body; mock mode makes no HTTP request and records nothing.

**Interfaces & Data Contracts:**
```python
class LlmError(RuntimeError):
    retryable: bool

async def call_openrouter(
    model: str, messages: list[dict[str, str]], *, temperature: float = 0.0,
    max_tokens: int = 500, json_mode: bool = False,
) -> tuple[str, dict[str, int]]:   # usage: {"prompt_tokens": int, "completion_tokens": int}

async def query_llm(
    prompt: str, model: str, system_prompt: str | None = None, temperature: float = 0.0,
    max_tokens: int = 500, *, json_mode: bool = False, node: str = "", tenant_id: str = "",
) -> str
```
`llm_calls` document: `{tenant_id, node, model, latency_ms: int, prompt_tokens: int, completion_tokens: int, ok: bool, error_type: str | None, ts: datetime (naive UTC)}`.

**Edge Cases:** provider omits `usage` → record zeros; empty `choices` → non-retryable `LlmError`; fallback model unset → retry on the same model; total worst case ≈ 2 × 8 s per node.

**Non-Goals:** No change to `get_mock_response` or to when the mock is selected. No prompt changes. No streaming, caching or rate limiting. No dashboard for telemetry.

**Acceptance Criteria:** new tests pass; existing `query_llm` tests pass unchanged (positional parameters preserved); mock eval 25/25; tenant-isolation grep empty.

**Verification:**
```bash
uv run pytest -q tests/test_llm_client.py tests/test_fixed_findings.py
uv run ruff check . && uv run mypy app && uv run pytest -q
uv run python evals/run_evals.py --ci --report artifacts/mock-eval-report.json
```

**Risk & Rollback:** Medium. A shared client can outlive an event loop in tests — if you see "Event loop is closed", reset the client in a fixture via `set_http_client(None)`. Some models reject `response_format`; `LLM_JSON_MODE=false` turns it off. Rollback = revert.

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** Existing tests depend on a new `httpx.AsyncClient` being created per call; adding the `LlmCalls` accessor would require raw `db[...]` access outside `app/models/`.

**Standalone Execution Prompt:**
```
Task W2-04 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet fully.
Rework app/agent/llm.py real path only (never touch get_mock_response or the mock selection):
- one lazily created shared httpx.AsyncClient (timeout settings.llm_timeout_seconds=8.0,
  connect 3.0) + set_http_client() for tests;
- public call_openrouter(model, messages, *, temperature, max_tokens, json_mode)
  -> (text, usage) making ONE attempt, raising LlmError(retryable) (retryable: timeout,
  transport error, 429, >=500);
- query_llm gains keyword-only json_mode, node, tenant_id; one retry on retryable errors using
  settings.llm_model_fallback_provider or the same model; response_format json_object when
  json_mode and settings.llm_json_mode;
- record every real attempt via _record_call into a new tenant-scoped accessor LlmCalls
  ("llm_calls": tenant_id,node,model,latency_ms,prompt_tokens,completion_tokens,ok,error_type,ts;
  TTL 30 days) - never store prompt/response text, never let telemetry raise.
Pass node/tenant_id from intent.py (json_mode=True) and responder.py. Add the two settings to
config.py and .env.example. Add tests/test_llm_client.py with httpx.MockTransport per the packet.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q && the mock eval (25/25).
Stop and report on the escalation conditions in the packet.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
