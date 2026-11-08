# Restore runbook

Target: RTO at most 15 minutes and RPO at most 1 hour. A timed restore to the
actual staging topology is required before pilot; the synthetic CI drill does
not satisfy that release gate.

## Preconditions

- The deployment operator verifies that continuous MongoDB backup is enabled
  for the production cluster and records its region, retention, and latest
  restorable point. This repository contains no evidence that it is enabled.
- MongoDB is the source of truth. Redis contains rebuildable dispatch, lock,
  and session state and is not restored from a snapshot.
- Keep the erasure case ledger and hashed suppression export outside the
  application backup set, as described in `docs/erasure-runbook.md`.
- Record the exact release image digest, backup identifier, backup timestamp,
  restore target, operator, and drill start time before making changes.

## Timed staging drill

1. Choose a restorable point no more than one hour old. Record its provider
   backup identifier and timestamp.
2. Pause ingress, API writes, workers, and scheduled jobs. Do not acknowledge
   provider events during the incompatible restore window.
3. Restore MongoDB into a fresh staging cluster. Never overwrite the source
   cluster or an existing staging database.
4. Point the recorded release image at the restored MongoDB and a fresh empty
   Redis instance. Keep ingress and outbound delivery disabled.
5. Import the latest hashed erasure-suppression export and replay erasure cases
   completed after the selected backup point.
6. Start only the worker. Verify that durable queued work in MongoDB drains,
   Redis consumer groups and heartbeat are recreated, exhausted work remains
   visible, and a suppressed synthetic recipient cannot be sent to.
7. Start the API and enable ingress. Verify `/health`, one tenant read, one
   synthetic webhook round-trip, tenant isolation, dashboard login, and worker
   heartbeat. Do not use real patient identifiers in drill evidence.
8. Record finish time, measured RTO, backup age/RPO, image digest, restored
   counts, queue reconciliation, suppression replay result, and rollback
   decision. Delete the isolated restore only after evidence is retained.

## Synthetic CI drill

The required `recovery-drill` job in `.github/workflows/ci.yml` uses
`mongodump` and `mongorestore` with isolated synthetic data, starts Redis empty,
then runs:

```text
python -m ops.recovery_drill seed
python -m ops.recovery_drill verify --report <path> --backup-id <sha256> --started-at-epoch <unix-seconds>
```

The command refuses to run unless `APP_ENV=dev`, `USE_MOCK_ADAPTERS=true`,
`RECOVERY_DRILL_CONFIRM=synthetic`, and the database name is exactly
`vaani_recovery_drill`. Its report is mechanics evidence only, not proof of
Atlas configuration, provider RPO, staging networking, or production-scale
restore time.

## Drill log

| Date | Environment | Operator | Backup ID/time | Image digest | RTO | RPO | Result/evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8 November 2026 | Synthetic GitHub Actions | Codex | `sha256:4b1b186e009dc7e0180cbe37086d1f32a8853d6cff6c8f7f29b9ce590930aced` | `sha256:0941a5088caba73e5208a3b01ea6bdf49bd82edfb72ae4cf34d060a3577d9e0c` | 1 second (synthetic) | Not established | Run `42478330865`, artifact `13616731369`; mechanics passed |
| _TBD before pilot_ | Staging | | | | | | Timed provider restore required |
