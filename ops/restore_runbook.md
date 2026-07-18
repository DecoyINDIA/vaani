# Restore Runbook

**Target:** RTO ≤ 15 min, RPO ≤ 1 hr (TRD §6, 06-engineering-plan Week 6 task 6.2).
Must be **tested once before pilot** — a timed restore to staging, logged here.

## Backups
- **MongoDB Atlas:** continuous backup enabled (ap-south-1). Source of truth.
- **Redis:** rebuildable state only (queue, locks, session cache) — NOT backed up.
- **Media:** purged at 30d (`MEDIA_PURGE_DAYS`); not part of restore.

## Restore procedure
1. Atlas → cluster → Backup → select point-in-time (within RPO 1h).
2. Restore to a fresh cluster / staging.
3. Point `MONGODB_URI` at the restored cluster.
4. `git pull && docker compose up -d --build` (Redis rebuilds itself).
5. Verify: `/health` OK, seed-tenant read, one webhook round-trip.

## Drill log
| Date | Operator | Restore time | RTO met? | Notes |
|------|----------|--------------|----------|-------|
| _TBD before pilot_ | | | | |
