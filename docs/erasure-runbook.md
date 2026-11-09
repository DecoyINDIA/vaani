# Patient erasure and DPDP retention runbook

Status: Implementation active and verified; statutory retention decisions and external ledger operations documented for production operation.

## Authority and SLA

Only an operator acting on a verified tenant request may apply erasure.
- **SLA**: Complete the request within seven (7) calendar days of verified identity/request receipt.
- **Accountability**: Record the verified case identifier as `request_id` and the accountable operator identity as `authorized_by`.
- **Zero-PII Evidence**: Never paste patient identifiers (phone, name, email, addresses) into tickets, logs, screenshots, or completion evidence. All evidence contains only counts, hashes, and case IDs.

## Statutory retention decisions & exceptions

Under Section 8(7) of the Digital Personal Data Protection (DPDP) Act, 2023, personal data must be erased upon withdrawal of consent or fulfillment of purpose, except where retention is mandated by law:

1. **Clinical & Conversation Records (Erased)**:
   - Contacts, WhatsApp/voice messages, conversations, waitlist entries, and escalations are deleted immediately upon applied erasure.
   - Active clinic booking appointments are deleted, and the associated slots are released (`status: "open"`, unlinked from booking) so clinics can reallocate capacity.
2. **Financial Records (Retained in Pseudonymized Form)**:
   - **Legal Basis**: Section 128 of the Companies Act, 2013 and Rule 3 of Prevention of Money Laundering (Maintenance of Records) Rules require books of account and vouchers to be retained for eight (8) years.
   - **Action**: In `payments` and `invoices`, records are retained with `contact_id: "[erased]"`, and any embedded patient names/numbers replaced with `"[erased]"`. Razorpay provider payment IDs, integer paise amounts, SAC 998313 classification, and GST calculation are preserved for accounting audits.
3. **Audit Log (Retained in Pseudonymized Form)**:
   - System audit trail records are scrubbed of patient identifiers and unlinked from conversations (`conversation_id` removed), preserving event metadata and timestamps.
4. **Suppression Markers (Irreversible Hashed Ledger)**:
   - To prevent an erased patient from receiving future reminders or being inadvertently re-created on subsequent webhooks, SHA-256 hashes (`identifier_hash(tenant_id, value)`) are stored in `erasure_suppression`. No raw plain-text is retained.

## Dry run

```powershell
.venv\Scripts\python.exe -m ops.dpdp_delete `
  --tenant <tenant-id> `
  --contact <contact-id-or-phone> `
  --request-id <case-id>
```

The report contains counts only. Review tenant scope, unlinked slots, and retained exceptions before applying.

## Apply and verify

```powershell
.venv\Scripts\python.exe -m ops.dpdp_delete `
  --tenant <tenant-id> `
  --contact <contact-id-or-phone> `
  --request-id <case-id> `
  --authorized-by <operator-id> `
  --provider-case-id whatsapp=<meta-ticket-id> `
  --provider-case-id exotel=<exotel-ticket-id> `
  --provider-case-id razorpay=<razorpay-ticket-id> `
  --apply
```

The action:
1. Removes contacts, conversations, messages, queued inbound payloads, bookings, waitlist entries, escalations, and temporary voice grants.
2. Unlinks slots booked by the patient and marks them `open`.
3. Pseudonymizes retained payment and audit rows.
4. Suppresses pending outbound delivery (`state: "suppressed"`, `to: "[erased]"`).
5. Stores hashed identifiers in `erasure_suppression`.
6. Refuses subsequent inbound WhatsApp messages and Exotel voice calls from the erased caller.
7. Re-running the same case is safe and reports `already_completed`.

## External provider deletion obligations

The operator must request downstream deletion or restriction from external providers under their established developer processes, recording provider case IDs in the erasure request:

| Provider | Data Held | Retention Policy & Deletion Procedure | Case ID Format |
| --- | --- | --- | --- |
| **Meta WhatsApp Cloud API** | Transient message payloads, phone numbers | 30-day operational retention on Meta infrastructure. Request deletion via Meta Business Support portal / Graph API user deletion endpoint. | `WABA-<id>` |
| **Exotel** | Call Detail Records (CDRs), voice audio recordings | Call recordings stored in customer vault/S3. Delete recording via Exotel REST API: `DELETE /v1/Accounts/{sid}/Recordings/{call_sid}`. | `EXO-<id>` |
| **Sarvam AI** | Utterance audio for STT and synthesized TTS audio | Ephemeral audio processing; zero data retention policy for API inference customers. | `SARVAM-<id>` |
| **Razorpay** | Customer phone, payment link records | 8-year statutory financial retention. Merchant can mask/anonymize customer identifiers via Merchant Dashboard or Razorpay API. | `RZP-<id>` |
| **MongoDB Atlas** | Automated continuous backups | Point-in-time continuous backups expire automatically after configured backup retention window (7 days). | `ATLAS-<id>` |

## External erasure ledger & restore replay

Keep the external erasure case ledger outside the application database backup set:

### Exporting the ledger

```powershell
.venv\Scripts\python.exe -m ops.erasure_ledger export --output /secure-ledger/erasure_ledger.json
```

The exported file contains only tenant IDs, request IDs, hashed identifiers, timestamps, and counts (zero raw PII).

### Replaying on a restored database

If MongoDB is restored from a backup taken before an erasure was executed:
1. Import the suppression markers and replay the erasure actions:
   ```powershell
   .venv\Scripts\python.exe -m ops.erasure_ledger replay --ledger /secure-ledger/erasure_ledger.json
   ```
2. Verify suppression on a synthetic test recipient:
   ```powershell
   .venv\Scripts\python.exe -m ops.erasure_ledger verify --tenant <tenant-id> --identifier <phone>
   ```
3. Only open API and worker traffic after the replay completes successfully.
