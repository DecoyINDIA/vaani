---
type: "Workflow"
title: "Human handoff"
description: "Escalation changes conversation ownership and coordinates staff notification."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/agent/nodes/handoff.py", "app/agent/tools/escalate.py", "docs/handoff.md", "tests/test_handoff.py", "tests/test_handoff_scheduling_alerts_acceptance.py"]
source_hashes: {"app/agent/nodes/handoff.py": "815bc41844bd2e068f45869dd166eb970320a6a9712beb59441d91191b729cbf", "app/agent/tools/escalate.py": "91b18f7076c59c284741458cdbe63884e60ad33ffe1858d1fb4aa63774511be4", "docs/handoff.md": "21fedc8c901082062ab5098e026debe994ec060b336d5a738f0fbde21bd6de16", "tests/test_handoff.py": "2b28da46c37f38d483c5d8e7595b11dc74090b55398f941e8c6efa8a9957573f", "tests/test_handoff_scheduling_alerts_acceptance.py": "7dd78dfe2badd830d4e70c67e81e9289b88eb284aa0ae7a29874bd118947bbb3"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/handoff.py", "title": "app/agent/nodes/handoff.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/tools/escalate.py", "title": "app/agent/tools/escalate.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/handoff.md", "title": "docs/handoff.md"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_handoff.py", "title": "tests/test_handoff.py"}, {"id": "s5", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_handoff_scheduling_alerts_acceptance.py", "title": "tests/test_handoff_scheduling_alerts_acceptance.py"}]
---
# Implemented path
The handoff node calls the escalation tool. Provider-failure state additionally creates an operational alert. Safety responses for medical, complaint, and abuse intents may be preserved while escalation proceeds.[^s1]

# Contract and limits
The handoff specification describes bot, human, and closed conversation states and resolve-and-return context. Its historical implementation notes are not current acceptance evidence.[^s3]

# Relationships
[Agent routing](agent-flow.md) initiates handoff. [Delivery](delivery.md) must respect human ownership; [tenant isolation](tenant-isolation.md) scopes conversation and staff access. [Retrieval](retrieval.md) uses escalation when facts cannot support a reply.

# Verify
Inspect takeover/send races, actual staff notification, on-duty scheduling, and SLA evidence. Use [release evidence](release-evidence.md) before claiming provider acceptance.

# Source references
[^s1]: [app/agent/nodes/handoff.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/handoff.py)
[^s2]: [app/agent/tools/escalate.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/tools/escalate.py)
[^s3]: [docs/handoff.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/handoff.md)
[^s4]: [tests/test_handoff.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_handoff.py)
[^s5]: [tests/test_handoff_scheduling_alerts_acceptance.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_handoff_scheduling_alerts_acceptance.py)
