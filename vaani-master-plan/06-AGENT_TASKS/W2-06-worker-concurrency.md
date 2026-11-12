### TASK ID: W2-06

> **Baseline note:** written against `847d5f5` with Wave 1 and W2-04 merged; locate code by symbol name.

**Title:** Process inbound events concurrently while keeping each patient's messages in order

**Priority:** P1

**Objective:** One worker process handles up to `WORKER_CONCURRENCY` (default 8) conversations at the same time; messages from the same patient are still processed strictly in arrival order; each process has a unique stream-consumer name; the agent graph is compiled once.

**Why This Matters:** The worker awaits one event at a time for the whole platform. Each event waits on LLM and WhatsApp calls, so one slow call delays every clinic's patients.

**Prerequisites:** Wave 1; W2-04 (the 8-second LLM timeout keeps an event inside its lease).

**Repository Context (read carefully — the loop has two intake paths):**
- `app/workers/inbound.py::run()` loop, per iteration: (1) `_process_fallback_queue()` — reads **all** Mongo messages with `status == "queued"` or an expired lease via `Messages.find_queued_unscoped()` (unsorted) and processes them **serially**; (2) heartbeat; (3) `xautoclaim` of stalled stream entries → `_handle`; (4) `xreadgroup(count=10, block=5000)` → `_handle` per entry, serially.
- Every accepted webhook message is both a `queued` Mongo document **and** a Redis stream entry, so path (1) usually processes messages before path (4) sees them; path (4) then fails to acquire and just acknowledges.
- `_handle(r, msg_id, fields, deliveries)`: `Messages.acquire_work_unscoped(durable_id)` (atomic lease, 60 s, increments `attempts`) → `process_event(fields)` → `mark_completed_unscoped` → `xack`; on exception `release_work_unscoped` and dead-letter when `deliveries >= MAX_DELIVERIES`.
- `process_event` begins with `app = build_graph()` on every message.
- `CONSUMER = "worker-1"` is a constant.
- The patient key is inside the payload: `json.loads(fields["payload"])["entry"][0]["changes"][0]["value"]["messages"][0]["from"]`; Mongo queue documents carry `payload` (dict), `tenant_id`, `accepted_at`.
- Mongo is the queue of record; Redis is only a wake-up. Do not change that.

**Files to Inspect:** `app/workers/inbound.py` (entire `run`, `_handle`, `_process_fallback_queue`), `app/models/collections.py` (`Messages.*_unscoped`), `app/agent/graph.py`, `tests/test_durable_ingress.py`, `tests/test_inbound_loop.py`

**Files to Modify/Create:** `app/workers/inbound.py`; `app/models/collections.py` (lease length parameter, sorted scan); `app/config.py` + `.env.example` (`worker_concurrency: int = 8`); `tests/test_worker_concurrency.py` (new).

**Detailed Implementation Instructions:**
1. **Graph once:** module-level `_GRAPH: Any = None` and `def get_graph() -> Any` that compiles on first use; `process_event` calls `get_graph()`.
2. **Unique consumer:** `CONSUMER = f"{socket.gethostname()}-{os.getpid()}"` computed at import.
3. **Lease:** give `Messages.acquire_work_unscoped` a keyword `lease_seconds: int = 60`; the worker passes `180`. `find_queued_unscoped` sorts by `accepted_at` ascending (then `_id`).
4. **Ordering key:** `def _contact_key(tenant_id: str, payload: dict[str, Any]) -> str` → `f"{tenant_id}:{sender}"`; when the sender cannot be read, use `f"{tenant_id}:{message_id}"` (its own group).
5. **Batch runner:**
```python
async def _run_grouped(items: list[T], key: Callable[[T], str],
                       handler: Callable[[T], Awaitable[None]], limit: int) -> None:
    groups: dict[str, list[T]] = {}          # insertion order preserved
    for item in items: groups.setdefault(key(item), []).append(item)
    sem = asyncio.Semaphore(limit)
    async def run_group(group: list[T]) -> None:
        async with sem:
            for item in group:               # sequential inside a patient
                try: await handler(item)
                except Exception: logger.exception("event handler failed")
    await asyncio.gather(*(run_group(g) for g in groups.values()))
```
   The runner returns only when the whole batch is finished, so the next batch for the same patient cannot overtake.
6. **Apply it to all three intake paths:** fallback scan (items = queued docs, already sorted; cap at 50 per iteration), reclaimed entries, and new stream entries (raise `count` to `2 * worker_concurrency`). The per-item handlers are today's bodies unchanged (acquire → process → complete/release, dead-letter rules intact).
7. Keep the heartbeat write once per loop iteration. Because a batch can now take longer, also refresh the heartbeat inside `_run_grouped` after each completed group (pass a small callback or do it in the handler wrapper) so the health check does not flap.
8. **Tests** (monkeypatch `process_event` with an instrumented fake that sleeps): 8 events from 8 patients finish in roughly one sleep, not eight (assert `max concurrent ≥ 4`); 5 events from one patient run strictly in `accepted_at` order with `max concurrent == 1` for that key; a failing event does not stop its group's later events nor other groups; a duplicate delivery of the same message id is processed once (lease); `CONSUMER` differs between two simulated PIDs; `get_graph()` returns the same object twice.

**Interfaces & Data Contracts:** `WORKER_CONCURRENCY` env (int ≥ 1; `1` reproduces today's serial behaviour — the rollback switch). No schema change.

**Edge Cases:** a patient sends two messages that land in different loop iterations → the first batch finishes before the second is read, so order holds; lease expiry during a very slow event → another intake path may re-acquire (existing behaviour; the 180 s lease makes it rare); Redis down → fallback scan still drains with concurrency.

**Non-Goals:** **Running more than one worker replica is still unsupported for ordering** — say so in a comment above `CONSUMER` and in your report; a distributed per-contact lock is a later task. No change to dead-letter thresholds, to `process_event` logic, or to the scheduler (W2-07).

**Acceptance Criteria:** new tests pass; `tests/test_durable_ingress.py` passes unchanged; with `WORKER_CONCURRENCY=1` behaviour is identical to before (run the full suite once with that env var set); full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_worker_concurrency.py tests/test_durable_ingress.py tests/test_inbound_loop.py
WORKER_CONCURRENCY=1 uv run pytest -q
uv run ruff check . && uv run mypy app && uv run pytest -q
```
The existing CI kill-tests (process killed mid-message, recovery) must stay green on the PR.

**Risk & Rollback:** High — concurrency in the delivery path. Failure modes to look for in review: two handlers for one patient running at once; an exception swallowed without `release_work_unscoped`; duplicate sends (prevented by `operation_key`, verify). Rollback without redeploy: `WORKER_CONCURRENCY=1`.

**Effort & Complexity:** Large effort, high reasoning.

**Recommended Agent Tier:** Advanced agent required; independent review required.

**Escalation Conditions:** The CI kill-tests fail; `tests/test_durable_ingress.py` needs assertion changes; you find a fourth intake path not described here; mongomock cannot express the sorted scan.

**Standalone Execution Prompt:**
```
Task W2-06 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this entire packet. High-risk change
to app/workers/inbound.py.
Goal: concurrent processing across patients, strict order within a patient, in ONE process.
1. get_graph(): compile the LangGraph app once; process_event uses it.
2. CONSUMER = f"{socket.gethostname()}-{os.getpid()}".
3. Messages.acquire_work_unscoped(..., lease_seconds=60) -> worker passes 180;
   find_queued_unscoped sorts by accepted_at then _id.
4. Add _contact_key(tenant_id, payload) and the _run_grouped helper from the packet (group by
   patient, sequential inside a group, groups concurrent under a semaphore of
   settings.worker_concurrency (default 8), gather before returning, exceptions logged per item).
5. Use _run_grouped for all three intake paths in run(): the Mongo fallback scan (max 50 per
   iteration), xautoclaim results, and xreadgroup results (count = 2 * concurrency). Keep the
   existing acquire -> process -> complete/release and dead-letter logic per item. Refresh the
   heartbeat after each completed group.
6. Add tests/test_worker_concurrency.py per the packet. WORKER_CONCURRENCY=1 must behave exactly
   as before (run the whole suite once with it).
Out of scope: multiple worker replicas (add a comment saying ordering is not guaranteed across
processes), process_event logic, scheduler.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q ; WORKER_CONCURRENCY=1 uv run pytest -q
Stop and report on any escalation condition.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
