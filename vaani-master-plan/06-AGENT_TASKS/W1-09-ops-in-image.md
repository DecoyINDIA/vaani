### TASK ID: W1-09

**Title:** Ship the `ops/` operator CLIs inside the container image

**Priority:** P1

**Objective:** `python -m ops.onboard_tenant --help` (and the other `ops` modules) run inside the built image.

**Why This Matters:** Tenant onboarding, DPDP erasure, secret rotation and migration are all `ops/*.py` scripts, but the Dockerfile copies only `app/`. In production the secrets and network access live in the container, so the tools cannot run where they are needed.

**Prerequisites:** None.

**Repository Context:**
- `Dockerfile`: stage 2 has `WORKDIR /srv`, `COPY app ./app`, `uv sync --frozen --no-dev --no-editable`, `COPY --from=dashboard /src/dist ./dashboard/dist`, then `chown -R appuser:appgroup /srv`.
- `ops/__init__.py` exists; scripts import from `app.*` (e.g. `ops/onboard_tenant.py` uses the booking engine) and use `argparse`.
- `ops/` also contains Markdown runbooks and an example JSON config — harmless to include.

**Files to Inspect:** `Dockerfile`, `ops/onboard_tenant.py` (top-level imports and `_main`), `.dockerignore` if present

**Files to Modify/Create:** `Dockerfile` only.

**Detailed Implementation Instructions:**
1. Add `COPY ops ./ops` immediately after the `COPY --from=dashboard …` line and before the `chown` line, so ownership is applied.
2. If a `.dockerignore` exists and excludes `ops`, remove that exclusion; otherwise do not create one.
3. Change nothing else in the Dockerfile.

**Interfaces & Data Contracts:** none.

**Edge Cases:** importing `ops.onboard_tenant` imports `app.config`; with `APP_ENV` unset it is `dev`, so no runtime validation fires on `--help`.

**Non-Goals:** No changes to `ops/` scripts, `pyproject.toml`, compose, or CI workflows. Do not package `ops` into the wheel.

**Acceptance Criteria:** the image builds; the command below exits 0 and prints argparse usage.

**Verification:**
```bash
docker build -t vaani:w1-09 .
docker run --rm vaani:w1-09 python -m ops.onboard_tenant --help
```
If Docker is unavailable in your environment, say so explicitly under RESULTS ("not verified — Docker unavailable") rather than claiming success, and include the Dockerfile diff as evidence.

**Risk & Rollback:** Low. Rollback = revert.

**Effort & Complexity:** Small, trivial reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** `--help` fails inside the image because an `ops` module needs a dev-only dependency or a network connection at import time — report the traceback; do not add dependencies.

**Standalone Execution Prompt:**
```
Task W1-09 in the Vaani repo. Read 07-AGENT_CONTEXT.md first.
The Dockerfile copies only app/ so the operator CLIs in ops/ are missing from the image.
Edit Dockerfile only: add the line  COPY ops ./ops  right after
"COPY --from=dashboard /src/dist ./dashboard/dist" and before the chown line.
If .dockerignore excludes ops, remove that entry. Change nothing else.
Verify: docker build -t vaani:w1-09 . && docker run --rm vaani:w1-09 python -m ops.onboard_tenant --help
(exit code 0, usage text printed). If Docker is not available, report "not verified" - do not
claim success.
Stop and report if the command fails for an import/dependency reason; do not add dependencies.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
