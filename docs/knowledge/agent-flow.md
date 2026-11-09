---
type: "Workflow"
title: "Message and agent flow"
description: "Scope routing connects tools, grounded replies, and handoff."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/agent/graph.py", "app/agent/nodes/scope_gate.py", "app/agent/nodes/tool_router.py", "tests/test_phase3.py"]
source_hashes: {"app/agent/graph.py": "b6faaffe2d04b14ed04c3caa2ee6c00326b606d0091838f8bcd5a118e4275cc5", "app/agent/nodes/scope_gate.py": "123354ba42e8f8e529a8e3f6df7453026a505b62ba78756e1eb557b09e0b84e4", "app/agent/nodes/tool_router.py": "8f68ab6dd234974886a74223bd7708dd36ea78b64c3c0a7e49da02637bbc5b90", "tests/test_phase3.py": "4be9207377566036c02e4779d415ba2715056d9ceb0d1f5110b2959258a552e4"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/graph.py", "title": "app/agent/graph.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/scope_gate.py", "title": "app/agent/nodes/scope_gate.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/tool_router.py", "title": "app/agent/nodes/tool_router.py"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_phase3.py", "title": "tests/test_phase3.py"}]
---
# Implemented flow
The graph starts with language detection, intent classification, and scope gating. Escalation goes to handoff; an existing static response goes to the output gate; other requests go through tool routing. Both tool routing and the responder can request escalation. The output gate can request a responder retry.[^s1]

# Change impact
- Tool selection and facts depend on [retrieval](retrieval.md) and [booking](booking.md).
- Escalation transfers control through [handoff](handoff.md).
- The graph is executed within the [delivery worker](delivery.md), which owns receipt and delivery concerns outside the graph.
- All data paths depend on [tenant isolation](tenant-isolation.md).

# Verify before changing
Inspect the graph edges and scope-gate implementation, then select scope and routing regressions. The existence of a test file is not evidence that its current run passes. Check the [release evidence](release-evidence.md) for recorded acceptance gaps.

# Source references
[^s1]: [app/agent/graph.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/graph.py)
[^s2]: [app/agent/nodes/scope_gate.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/scope_gate.py)
[^s3]: [app/agent/nodes/tool_router.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/tool_router.py)
[^s4]: [tests/test_phase3.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_phase3.py)
