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

## Status

Pre-code. Currently in Phase 0 (validation) per [03-build-plan.md](03-build-plan.md) — no product code ships before 5 signed pilot LOIs.

## Ship criteria (binary gates — see 03-build-plan.md and 06-engineering-plan.md for detail)

- **G0 (before any code):** ≥5 signed LOIs, WABA verification submitted, pricing memo confirms >60% Starter gross margin.
- **Every PR:** lint + typecheck + unit tests + tenant-isolation suite pass; prompt/taxonomy changes additionally require the eval suite to pass (intent F1 ≥ threshold, hallucination incidents = 0).
- **G1 (pilot exit):** containment ≥60%, booking conversion ≥50%, hallucination incidents = 0.
- **G2 (voice exit):** COGS ≤₹4/min, containment ≥50%, no open compliance/legal items.

## Environment

Copy `.env.example` → `.env` and fill in per the comments (grouped by TRD ADR). Never commit `.env`.

## License

Proprietary — Xolver / Subham Jena. All rights reserved.
