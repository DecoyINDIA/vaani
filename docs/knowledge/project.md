---
type: "Project"
title: "Vaani project map"
description: "What Vaani does and where to start a change."
status: "draft"
generated: {"by": "codex/booking-impact-map", "at": "2026-11-09T11:38:56.821259+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["README.md", "00-overview.md"]
source_hashes: {"README.md": "a02d6262644b7d7a7c7954a366276d1537701df5febd15263da5abd056f2d49b", "00-overview.md": "35606f7ded03fba43c3171207021f907e336bf6a953e7ba407849de64a19477c"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/README.md", "title": "README.md"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/00-overview.md", "title": "00-overview.md"}]
---
# Purpose
Vaani is a WhatsApp and voice front-desk agent for appointment-driven Indian SMBs, starting with clinics. This bundle describes engineering knowledge, not patient records or approved clinic facts.[^s1]

# Start with a question
- How does a message become a reply? Follow the [agent flow](agent-flow.md) and [delivery](delivery.md).
- Where do we protect clinic boundaries? Read [tenant isolation](tenant-isolation.md).
- Where can booking break? Follow [booking](booking.md) to [release evidence](release-evidence.md).
- What facts can the agent answer? Read [retrieval and grounding](retrieval.md).
- How do we keep this useful? Follow [maintenance](maintenance.md).

# Boundary
Use the [product retrieval plan](product-retrieval-plan.md) when we move from engineering knowledge into clinic-facing knowledge. A graph link describes a relationship; it does not grant access or establish truth.

# Source references
[^s1]: [README.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/README.md)
[^s2]: [00-overview.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/00-overview.md)

# Deep-dive entry point
For a booking or MongoDB identifier change, start at [booking impact](booking-impact.md), then [identifier contracts](identifier-contracts.md) and [booking evidence](booking-evidence.md).
