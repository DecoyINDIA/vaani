---
type: "Workflow"
title: "Durable receipt and delivery"
description: "MongoDB durable work and Redis dispatch connect provider ingress to replies."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/gateway/meta.py", "app/workers/inbound.py", "app/channels/whatsapp.py", "tests/test_durable_ingress.py", "tests/test_outbound_delivery.py", "docs/production-remediation-plan.md"]
source_hashes: {"app/gateway/meta.py": "5adb6c7e12419ce8abcdf9a022dbb3483db5e7efccd6aa25de81e756c610667f", "app/workers/inbound.py": "f705f3dedcd07ae9644eaef9f185463469ba78e3f8ead983095adb5bebb88d75", "app/channels/whatsapp.py": "b6b1fdd4bd35a8cdacbea367cc130707c6c662390e4c4b7b27998a488c13b1dc", "tests/test_durable_ingress.py": "c4a61a2bb696c2bb0945dd5dc81a9830b830b5d7e73ab11fd36043b365a1f5c1", "tests/test_outbound_delivery.py": "80ddbb9707044c890e95990c9e41eeb99e983b8306fc9f1c93e79e53ca58285c", "docs/production-remediation-plan.md": "4b5827eea80bda1458e34fa497a99f1bf3296a8d6bb4a7f66ba876ebeffe6573"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/gateway/meta.py", "title": "app/gateway/meta.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/workers/inbound.py", "title": "app/workers/inbound.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/channels/whatsapp.py", "title": "app/channels/whatsapp.py"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_durable_ingress.py", "title": "tests/test_durable_ingress.py"}, {"id": "s5", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_outbound_delivery.py", "title": "tests/test_outbound_delivery.py"}, {"id": "s6", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md", "title": "docs/production-remediation-plan.md"}]
---
# Architecture and acceptance contract
The remediation plan specifies MongoDB as durable receipt/work storage and Redis as rebuildable dispatch. Outbound intent has explicit states; ambiguous sends require reconciliation or operator review rather than blind retries. This is an acceptance contract, not a blanket exactly-once guarantee.[^s6]

# Trace a failure
Start at Meta ingress, follow the inbound worker, then inspect the WhatsApp sender and durable delivery tests.[^s1][^s2][^s3]

# Relationships
Processing invokes the [agent graph](agent-flow.md). Booking notifications depend on [booking](booking.md); human-owned conversations depend on [handoff](handoff.md); provider and clinic selection depend on [tenant boundaries](tenant-isolation.md).

# Pending proof
Real two-clinic WhatsApp journeys and live-provider delivery evidence remain governed by [release evidence](release-evidence.md).

# Source references
[^s1]: [app/gateway/meta.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/gateway/meta.py)
[^s2]: [app/workers/inbound.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/workers/inbound.py)
[^s3]: [app/channels/whatsapp.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/channels/whatsapp.py)
[^s4]: [tests/test_durable_ingress.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_durable_ingress.py)
[^s5]: [tests/test_outbound_delivery.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_outbound_delivery.py)
[^s6]: [docs/production-remediation-plan.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md)
