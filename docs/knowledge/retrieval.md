---
type: "Subsystem"
title: "Retrieval and grounded answers"
description: "Tenant-filtered KB search feeds cited facts to the responder and output gate."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/kb/retrieval.py", "app/agent/nodes/responder.py", "app/agent/nodes/output_gate.py", "tests/test_grounding_retrieval_acceptance.py", ".github/workflows/credentialed-retrieval.yml"]
source_hashes: {"app/kb/retrieval.py": "bed1db0beb9ea8a67a3705907efa88140afd744a56a23665a38e085bd43044e8", "app/agent/nodes/responder.py": "f22a8093fe41eeb0d1b161652e18ae1233cea1ad5dd3f115bcdb47ca13b041da", "app/agent/nodes/output_gate.py": "0a9067fe9c02847053c9911cbb4383c0165681e933c37b0755a21791243af0dc", "tests/test_grounding_retrieval_acceptance.py": "2ba2ad1527c19e4b17a089fd3ea2c6bdcbffb7440593cd7fe0608e4e001b9afe", ".github/workflows/credentialed-retrieval.yml": "009b8657bdfdf273e27d6c15fb438e48e127a7f217c76dac53b0ec79e20a0e25"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/kb/retrieval.py", "title": "app/kb/retrieval.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/responder.py", "title": "app/agent/nodes/responder.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/output_gate.py", "title": "app/agent/nodes/output_gate.py"}, {"id": "s4", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_grounding_retrieval_acceptance.py", "title": "tests/test_grounding_retrieval_acceptance.py"}, {"id": "s5", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/.github/workflows/credentialed-retrieval.yml", "title": ".github/workflows/credentialed-retrieval.yml"}]
---
# Implemented retrieval
hybrid_search uses the tenant-scoped KbEntries accessor and query embeddings. Mock mode or a missing embedding model selects a structured-key fallback. Retrieval errors also degrade to that fallback; an absent fallback key yields no facts.[^s1]

# Grounding
The responder builds Grounded Facts from KB and slot tool results and asks for source_ref citations. The output gate checks citation references against tool-provided sources and checks numeric support, including localized digits. These checks have limits and do not prove universal factual correctness.[^s2][^s3]

# Relationships
Search depends on [tenant isolation](tenant-isolation.md); facts enter the [agent flow](agent-flow.md). LLM errors can route to [handoff](handoff.md). [Release evidence](release-evidence.md) distinguishes simulated retrieval checks from credentialed, real-model acceptance.

# Product extension
Follow the [product retrieval plan](product-retrieval-plan.md). The engineering bundle must never be loaded wholesale into patient-facing answers.

# Source references
[^s1]: [app/kb/retrieval.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/kb/retrieval.py)
[^s2]: [app/agent/nodes/responder.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/responder.py)
[^s3]: [app/agent/nodes/output_gate.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/agent/nodes/output_gate.py)
[^s4]: [tests/test_grounding_retrieval_acceptance.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_grounding_retrieval_acceptance.py)
[^s5]: [.github/workflows/credentialed-retrieval.yml](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/.github/workflows/credentialed-retrieval.yml)
