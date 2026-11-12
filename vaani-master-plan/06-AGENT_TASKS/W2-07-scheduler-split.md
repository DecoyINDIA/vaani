### TASK ID: W2-07

> **Baseline note:** written against `847d5f5` with Wave 1 and W2-06 merged; locate code by symbol name.

**Title:** Run scheduled jobs in their own process; let failed slot-expansion jobs retry

**Priority:** P1

**Objective:** Reminders, slot expansion, escalation SLAs, summaries and invoicing run from `python -m app.workers.scheduler` as a separate Compose service with its own heartbeat. A slot-expansion run that failed or crashed can be retried the same day.

**Why This Matters:** The scheduler is an `asyncio` task inside the message consumer. If the consumer is busy, restarting, or crashes, reminders stop with it. And a `slot_expansion` job row left in `failed` or `running` blocks any retry until the next local day, so a clinic can silently run out of bookable slots.

**Prerequisites:** W2-06 (same file), W1-08 (`ENABLE_BILLING`).

**Repository Context:**
- `app/workers/inbound.py::run_scheduler_background()` — an endless loop: stale-send reconciliation (`OutboundIntents.mark_stale_sending_unknown_unscoped` + alert), `run_schedule_expansion()`, `run_reminders()`, `run_escalation_slas()`, `run_monthly_invoices()`, `run_weekly_summaries()`, then `asyncio.sleep(15 * 60)`. Each step has its own `try/except`.
- `run()` starts it with `asyncio.create_task(run_scheduler_background())` and cancels it in `finally`.
- `app/booking/engine.py::run_schedule_expansion`: inserts a `JobRuns` row `_id = f"slot-expansion:{tenant_id}:{local_date}"` with `state: "running"`; on `DuplicateKeyError` it **skips** the tenant; sets `completed` or `failed` at the end.
- `app/workers/healthcheck.py`: reads Redis key `vaani:worker:heartbeat`, alerts and exits non-zero when older than 60 s. The worker sets that key each loop.
- `docker-compose.yml`: services `api`, `worker` (with the healthcheck), `redis`.
- Weekly summaries fire only when the tenant-local time is Sunday 23:xx, so the tick must stay well under an hour.

**Files to Inspect:** `app/workers/inbound.py`, `app/booking/engine.py`, `app/workers/healthcheck.py`, `docker-compose.yml`, `app/config.py`, tests referencing `run_scheduler_background` (`grep -rn "run_scheduler_background" tests`)

**Files to Modify/Create:**
- `app/workers/scheduler.py` — new entrypoint.
- `app/workers/inbound.py` — remove the embedded task; keep a compatibility import.
- `app/booking/engine.py` — retry rule in `run_schedule_expansion` only.
- `app/workers/healthcheck.py` — optional key argument.
- `app/config.py`, `.env.example` — `scheduler_interval_seconds: int = 300`.
- `docker-compose.yml` — `scheduler` service.
- `tests/test_scheduler.py` — new.

**Detailed Implementation Instructions:**
1. Create `app/workers/scheduler.py`:
   - `async def run_once(*, now: datetime | None = None) -> dict[str, str]` — runs the six steps in today's order, each in its own `try/except` that logs with `exc_info=True`; returns `{step_name: "ok" | "error" | "skipped"}`. Run `run_monthly_invoices` only when `settings.enable_billing`, otherwise `"skipped"`.
   - `async def run_scheduler_background() -> None` — `while True: await run_once(); set heartbeat; await asyncio.sleep(settings.scheduler_interval_seconds)`. Heartbeat: Redis `SET vaani:scheduler:heartbeat <epoch> EX <3 × interval>`, wrapped in `try/except`.
   - `def main()` — `settings.validate_runtime()`, logging setup identical to the worker's, `asyncio.run(run_scheduler_background())`; `if __name__ == "__main__": main()`.
2. `inbound.py`: delete the function body and the `create_task`/`cancel` lines from `run()`; add `from app.workers.scheduler import run_scheduler_background  # noqa: F401` so existing imports keep working. Confirm no circular import (the scheduler module must not import `app.workers.inbound`).
3. `engine.py::run_schedule_expansion`: on `DuplicateKeyError`, try to **take over** the row atomically:
```python
stale_before = now_utc_naive - timedelta(minutes=30)
taken = await jobs.find_one_and_update(
    {"_id": job_id, "$or": [{"state": "failed"},
                            {"state": "running", "started_at": {"$lt": stale_before}}]},
    {"$set": {"state": "running", "started_at": now_utc_naive}, "$inc": {"retries": 1}},
)
if not taken: stats["skipped"] += 1; continue
```
   then proceed with the expansion as for a fresh row. `completed` rows are still skipped.
4. `healthcheck.py`: accept an optional first CLI argument naming the heartbeat key and an optional second argument for the maximum age in seconds; defaults preserve today's behaviour (`vaani:worker:heartbeat`, 60). Use the key name in the alert payload (`"component": <key>`), no PII.
5. `docker-compose.yml`: add
```yaml
  scheduler:
    build: .
    command: python -m app.workers.scheduler
    env_file: .env
    depends_on: [redis]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-m", "app.workers.healthcheck", "vaani:scheduler:heartbeat", "900"]
      interval: 60s
      timeout: 5s
      retries: 3
```
6. Tests: `run_once` calls each step once in order (monkeypatch the six functions); one step raising does not prevent the rest and is reported `"error"`; invoices `"skipped"` when `enable_billing` is false; `run_schedule_expansion` retries a `failed` row and a `running` row older than 30 minutes, skips a fresh `running` row and a `completed` row; `inbound.run(iterations=1)` no longer invokes any scheduled job.

**Interfaces & Data Contracts:** `SCHEDULER_INTERVAL_SECONDS` (default 300). `job_runs` gains optional `retries: int`. Redis key `vaani:scheduler:heartbeat`.

**Edge Cases:** two scheduler containers started by mistake → reminders and summaries rely on their existing per-item idempotency (operation keys / `reminder_status`); slot expansion relies on the job row; do **not** scale this service above one — state that in a compose comment.

**Non-Goals:** No cron library, no new job types, no change to what reminders/summaries/invoices do, no change to the worker loop beyond removing the task.

**Acceptance Criteria:** tests pass; `grep -n "create_task(run_scheduler_background" app/workers/inbound.py` prints nothing; `docker compose config` validates; full suite green.

**Verification:**
```bash
uv run pytest -q tests/test_scheduler.py tests/test_schedule_expansion.py tests/test_handoff_scheduling_alerts_acceptance.py
uv run ruff check . && uv run mypy app && uv run pytest -q
docker compose config >/dev/null
```

**Risk & Rollback:** Medium — a deployment that does not start the new service sends no reminders. The release note must say "start the `scheduler` service". Rollback = revert (scheduler returns to the worker).

**Effort & Complexity:** Medium effort, moderate reasoning.

**Recommended Agent Tier:** Medium-capability agent

**Escalation Conditions:** A test starts `inbound.run()` and relies on scheduled jobs firing; importing the scheduler from `inbound.py` creates a cycle; mongomock rejects the take-over update.

**Standalone Execution Prompt:**
```
Task W2-07 in the Vaani repo. Read 07-AGENT_CONTEXT.md and this packet. Base on W2-06.
1. Create app/workers/scheduler.py with run_once() (the six steps currently inside
   inbound.run_scheduler_background, same order, each try/except, invoices only if
   settings.enable_billing), run_scheduler_background() (loop: run_once, set Redis heartbeat
   vaani:scheduler:heartbeat, sleep settings.scheduler_interval_seconds=300), and main().
2. app/workers/inbound.py: remove the embedded scheduler task from run(); re-export
   run_scheduler_background from the new module for compatibility. No import cycle.
3. app/booking/engine.py run_schedule_expansion: on DuplicateKeyError take over the job row when
   its state is "failed" or "running" with started_at older than 30 minutes (atomic
   find_one_and_update, $inc retries); otherwise skip as today.
4. app/workers/healthcheck.py: optional argv[1] heartbeat key and argv[2] max age seconds;
   defaults unchanged.
5. docker-compose.yml: add the scheduler service from the packet (single replica).
6. Add scheduler_interval_seconds to config.py and .env.example; add tests/test_scheduler.py.
Do NOT change reminder/summary/invoice logic or add libraries.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q ; docker compose config
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
