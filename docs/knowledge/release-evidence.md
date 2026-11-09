---
type: "Release Gate"
title: "Release evidence and open acceptance"
description: "The remediation ledger is authoritative for current acceptance status."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["docs/production-remediation-plan.md", "docs/production-review.md", ".github/workflows/ci.yml"]
source_hashes: {"docs/production-remediation-plan.md": "4b5827eea80bda1458e34fa497a99f1bf3296a8d6bb4a7f66ba876ebeffe6573", "docs/production-review.md": "c8213bbbde3b9d185fdf00d94a37a34835773a9affdc39c23a8df776ff9b2606", ".github/workflows/ci.yml": "d63d34dafba61cca5c55966300a57ea83ce3886843e5c497c56513d7e5ab914b"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md", "title": "docs/production-remediation-plan.md"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-review.md", "title": "docs/production-review.md"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/.github/workflows/ci.yml", "title": ".github/workflows/ci.yml"}]
source_snapshot: "Reviewed local working tree on 2026-11-09; immutable citation URLs refer to the committed baseline, while fingerprints include the local changes noted below."
---
# Snapshot, not live status
At the inspected checkout, the remediation plan records completed implementation/CI milestones and pending final acceptance for all R01-R20 findings. The release decision is No go. This bundle does not independently rerun or verify the historical CI results.[^s1]

# Highest-impact threads
- R03/R17: trace generated-ID coverage and migration decisions through [tenant boundaries](tenant-isolation.md) and [booking](booking.md).
- R04/R05/R09/R12/R13/R18: trace two-clinic journeys through [delivery](delivery.md) and [handoff](handoff.md).
- R14: trace real-model/Atlas acceptance through [retrieval](retrieval.md).
- R20: use the actual remediation ledger and workflow evidence for release gates; never infer live-provider readiness from offline checks.

# Authority rule
Use the current remediation ledger for release status, current code for implemented behavior, and product/design documents for intended behavior. Record contradictions explicitly. This summary is navigational and remains a draft pending owner review.

# Source references
[^s1]: [docs/production-remediation-plan.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md)
[^s2]: [docs/production-review.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-review.md)
[^s3]: [.github/workflows/ci.yml](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/.github/workflows/ci.yml)

# Working-tree reconciliation
The current working tree adds invitation-token SPA and built-asset smoke assertions to CI. Their presence does not establish a successful run.
