# Patient erasure runbook

Status: implementation available for synthetic/local verification; retention policy, provider deletion, and restore-drill evidence still require responsible-owner approval.

## Authority and SLA

Only an operator acting on a verified tenant request may apply erasure. Record the case identifier as `request_id` and the accountable operator identity as `authorized_by`. Complete the request within the existing seven-calendar-day SLA. Never paste patient identifiers into tickets, logs, screenshots, or completion evidence.

## Dry run

```powershell
.venv\Scripts\python.exe -m ops.dpdp_delete `
  --tenant <tenant-id> `
  --contact <contact-id> `
  --request-id <case-id>
```

The report contains counts only. Review tenant scope and retained exceptions before applying.

## Apply and verify

```powershell
.venv\Scripts\python.exe -m ops.dpdp_delete `
  --tenant <tenant-id> `
  --contact <contact-id> `
  --request-id <case-id> `
  --authorized-by <operator-id> `
  --apply
```

The action removes contacts, conversations, messages, queued inbound payloads, bookings, waitlist entries, and escalations. It pseudonymizes retained payment and audit rows, suppresses pending outbound delivery, and stores only hashed identifiers in `erasure_suppression`. Re-running the same case is safe and reports `already_completed`.

Verify that the contact cannot be found in the tenant, no pending/unknown outbound intent still contains the recipient, and the same identifier remains untouched in a different tenant. Store only counts and the case ID as evidence.

## Retained records and providers

Payments, pseudonymized audit events, the erasure request, and hashed suppression markers are retained pending the approved financial/audit retention schedule. The responsible business owner must document the legal basis and period before production use.

The operator must separately request deletion or retention restriction from enabled WhatsApp/BSP, Exotel, STT/TTS, Razorpay, media, backup, and observability providers under their supported processes. Record provider case IDs without copying patient data.

## Restore handling

Keep the erasure case ledger and hashed suppression export outside the application backup set. Before reopening traffic after a restore, import the latest suppression markers, replay every erasure case completed after the restored snapshot, and run a synthetic cross-tenant verification. Do not start workers or outbound delivery until the replay completes. The release gate requires a timed staging restore proving this process; the local test suite does not substitute for that drill.
