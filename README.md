# Project Vaani

Vernacular AI front-desk agent (WhatsApp + voice) for Indian appointment-driven SMBs. v1 vertical: clinics.

Planning pack — read [00-overview.md](00-overview.md) first.

| Doc | Contents |
|-----|----------|
| [00-overview.md](00-overview.md) | Index, key decisions, Week-1 blockers, top risks |
| [01-PRD.md](01-PRD.md) | Problem, personas, goals, requirements, acceptance criteria |
| [02-TRD.md](02-TRD.md) | Architecture, ADRs, data model, agent design, NFRs, cost model |
| [03-build-plan.md](03-build-plan.md) | Phased business plan, milestones, gates, budget |
| [04-gtm-pricing.md](04-gtm-pricing.md) | Positioning, pricing, ICP, channels, funnel |
| [05-risk-compliance.md](05-risk-compliance.md) | Risk register, Meta/WhatsApp policy, DPDP, legal |
| [06-engineering-plan.md](06-engineering-plan.md) | End-to-end engineering execution: repo layout, week-by-week build, CI/eval gates |
| [Production review](docs/production-review.md) | Confirmed production findings, reproduction evidence, verification results, and review limits |
| [Production remediation plan](docs/production-remediation-plan.md) | Ordered fixes, acceptance criteria, migration/rollback steps, release gates, and completion ledger |

## Status

Implementation exists, but it is **not ready for production**. The 6 November 2026 review identified 20 open findings across authentication, booking, handoff, delivery, voice, billing, data handling, and release verification. Follow the [production remediation plan](docs/production-remediation-plan.md) for the current work order and release decision. Passing offline tests does not establish live-provider readiness.

The business validation gates in [03-build-plan.md](03-build-plan.md), including five signed pilot LOIs, remain separate prerequisites; this engineering review did not verify their completion.

## Ship criteria (binary gates — see 03-build-plan.md and 06-engineering-plan.md for detail)

- **G0 (before any code):** ≥5 signed LOIs, WABA verification submitted, pricing memo confirms >60% Starter gross margin.
- **Every PR:** lint + typecheck + unit tests + tenant-isolation suite pass; prompt/taxonomy changes additionally require the eval suite to pass (intent F1 ≥ threshold, hallucination incidents = 0).
- **G1 (pilot exit):** containment ≥60%, booking conversion ≥50%, hallucination incidents = 0.
- **G2 (voice exit):** COGS ≤₹4/min, containment ≥50%, no open compliance/legal items.

## Environment

Copy `.env.example` → `.env` and fill in per the comments (grouped by TRD ADR). Never commit `.env`.

## License

Proprietary — Xolver / Subham Jena. All rights reserved.
