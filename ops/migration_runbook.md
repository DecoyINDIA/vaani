# Database Migration and Backfill Runbook

This runbook guides operators through executing data inventory and resumable backfills
for Vaani database maintenance, closing R03 and R17 data migration requirements.

## 1. Preconditions & Safety Gates

1. **Production Backup Verification:**
   - Confirm a restorable point-in-time snapshot exists before initiating maintenance.
   - Record the provider backup snapshot ID, creation timestamp, and region.
   - Never run migrations directly against production without verifying the backup.
2. **Ingress and Worker Pause:**
   - Temporarily pause external ingress (WhatsApp webhook endpoints, Exotel call endpoints)
     or ensure reverse proxy queues/retries requests with HTTP 503/429 so provider events
     are not acknowledged and discarded during maintenance.
   - Stop background workers (`reminders`, `inbound`, `weekly_summary`, `billing`) to avoid
     concurrent mutations while normalizing references.

## 2. Step 1: Read-Only Data Inventory

Run the read-only inventory script on an isolated restored copy or directly on the database:

```bash
python -m ops.migration_inventory
```

The script produces a JSON report containing:
- `counts_by_tenant`: Total document counts per collection scoped by tenant.
- `id_types`: Primary `_id` types (`ObjectId` vs `str`).
- `ambiguous_ids`: Hex strings that collide with stored `ObjectId`s.
- `reference_types`: Foreign key types (`str` vs `ObjectId`).
- `orphan_references`: References pointing to non-existent target entities.
- `duplicate_contact_groups`: Duplicate phone/wa_id entries per tenant.
- `duplicate_active_conversation_groups`: Multiple bot/human threads for a single contact.
- `legacy_open_conversations`: Count of conversations in legacy `open` state.
- `slot_ownership`: Held slots without owner, or booked slots without booking ID.
- `timestamp_provenance`: Counts of aware, naive, and non-datetime values.

Inspect the inventory for:
- Any `ambiguous_ids` > 0: Requires explicit operator mapping before backfill.
- `orphan_references` > 0: Review whether orphan references belong to purged test accounts.
- Timestamp provenance: Verify whether naive timestamps reflect UTC or local time.

## 3. Step 2: Dry-Run Backfill

Run the migration in dry-run mode to project modifications without altering stored records:

```bash
python -m ops.resumable_migration --dry-run
```

Optionally scope to a single tenant:

```bash
python -m ops.resumable_migration --dry-run --tenant <tenant_id>
```

Verify that:
- Projected counts match the expectations from the inventory.
- `operator_review_required.ambiguous_collisions` is empty or understood.
- No unexpected destructive actions are planned.

## 4. Step 3: Apply Resumable Backfill

Execute the backfill with explicit confirmation:

```bash
python -m ops.resumable_migration --apply --confirm MIGRATE [--tenant <tenant_id>]
```

The backfill performs 5 discrete, atomic stages:
1. **State Normalization:** Updates all conversations where `state: "open"` to `state: "bot"`.
2. **Reference Normalization:** Normalizes foreign keys (`contact_id`, `conversation_id`,
   `slot_id`, `booking_id`) to match the canonical stored `_id` type (`ObjectId` or `str`)
   of the target record. Ambiguous collisions are skipped and logged.
3. **Slot Ownership & Hold Cleanup:**
   - Releases expired holds (`hold_expiry < now_utc`) back to `status: "open"`.
   - Links booked slots missing `booking_id` to their owning booking where unambiguous.
4. **Timestamp Normalization:** Parses unambiguous ISO string datetimes into native BSON UTC
   datetimes. Naive datetimes are preserved without guessing provenance.
5. **Stranded Work Classification:** Identifies and reports queued/placeholder messages.

## 5. Step 4: Verification and Idempotency Check

Re-run the migration to prove idempotency:

```bash
python -m ops.resumable_migration --apply --confirm MIGRATE
```

Expected result on second run:
- `conversation_states_normalized`: 0
- `references_normalized`: 0 across all relationships
- `expired_holds_released`: 0
- `slot_ownership_reconciled`: 0
- `timestamps_normalized`: 0

Run the test suite to verify application invariants:

```bash
pytest -q tests/test_resumable_migration.py tests/test_migration_inventory.py
```

## 6. Compatibility & Rollback Procedures

### Backward Compatibility Window
- The application code (`TenantScoped.resolve_id()`, `mongo_id_candidates()`) transparently
  accepts both `ObjectId` and legacy string identifiers at runtime.
- Reverting the application container image does NOT require rolling back normalized
  data, because the normalized data uses standard BSON types supported across all versions.

### Emergency Rollback (Data Restore)
If migration fails catastrophically or unrecoverable corruption is detected:
1. Keep ingress and workers paused.
2. Restore the database from the pre-migration snapshot verified in Step 1.
3. Re-apply any DPDP erasure suppression records logged in `erasure_suppression`
   since the snapshot was taken (see `ops/restore_runbook.md`).
4. Rebuild Redis cache and streams from the restored MongoDB state.
5. Restart workers and unpause ingress.
