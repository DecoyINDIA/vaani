# Billing operations runbook

## Configuration gate

Production startup requires `RAZORPAY_PLAN_STARTER_ID`, `RAZORPAY_PLAN_PRO_ID`,
and `XOLVER_GSTIN`. Provider plan IDs are mapped only to the canonical
`starter` and `pro` codes in `app/billing/plans.py`; an unknown ID is sent to
reconciliation and must never fall back to Starter.

The approved list prices currently recorded by the PRD, GTM plan, LOI, and
pricing memo are ₹2,999/month for Starter and ₹6,999/month for Pro, before 18%
GST. Pro includes 300 voice minutes and bills each started excess minute at ₹4.
Starter overages are ₹2 per conversation after 1,000 and ₹49 per confirmed
booking after 50. Code stores every amount in paise.

## Usage and period close

Producers must call `record_usage` with a stable provider or domain event ID,
one named metric, and an integer quantity in that metric's declared unit.
Retries with the same event ID are free. Voice usage is audio duration in
seconds; request latency is observability data and must not be billed.

Periods follow the tenant's IANA timezone. On the first local calendar day of a
month, the worker snapshots the previous month's immutable usage events and
creates one invoice record. A later plan change cannot rewrite that snapshot.
One tenant's invalid timezone, plan, or billing identity does not stop other
tenants: the worker records one PII-free `invoice_issuance_failed` operational
alert per tenant/period and retries on its next scan.

## Delivery and reconciliation

New invoice records deliberately begin with `delivery_status=pending`. Before
production billing is enabled, the responsible owner must approve the final GST
identity/SAC and the team must connect a real document renderer and delivery
provider. That provider must update the invoice to `delivered` with a stable
provider document/message ID, or to `failed` with a visible error. Pending or
failed invoices are a release blocker; operators must not mark them delivered
by hand without provider evidence.

For Razorpay subscription events, inspect `billing_subscriptions`, the tenant's
`billing_status`, and `subscription_updated` audit records. Unknown plan IDs,
missing tenant notes, and missing subscription IDs require reconciliation. Do
not edit the tenant plan to make a webhook pass; correct the provider mapping or
subscription and replay the signed event.
