---
type: "Proposal"
title: "Clinic knowledge retrieval next"
description: "A staged plan for using curated clinic knowledge inside Vaani."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["app/kb/retrieval.py", "app/models/collections.py", "tests/test_grounding_retrieval_acceptance.py"]
source_hashes: {"app/kb/retrieval.py": "bed1db0beb9ea8a67a3705907efa88140afd744a56a23665a38e085bd43044e8", "app/models/collections.py": "e18443ad6693cff6445447e5a6a0cbc38cb177818a1ebfbdae2926cf69bce8b1", "tests/test_grounding_retrieval_acceptance.py": "2ba2ad1527c19e4b17a089fd3ea2c6bdcbffb7440593cd7fe0608e4e001b9afe"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/kb/retrieval.py", "title": "app/kb/retrieval.py"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/collections.py", "title": "app/models/collections.py"}, {"id": "s3", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_grounding_retrieval_acceptance.py", "title": "tests/test_grounding_retrieval_acceptance.py"}]
source_snapshot: "Reviewed local working tree on 2026-11-09; immutable citation URLs refer to the committed baseline, while fingerprints include the local changes noted below."
---
# Proposed next slice
This page is a proposal, not implemented runtime behavior. Engineering knowledge comes first; [existing retrieval](retrieval.md) remains the runtime path.

1. Choose one clinic and one low-risk FAQ scope, such as approved opening hours, location, and service availability. The owner supplies and approves the actual facts; do not invent clinic data.
2. Define clinic-owned concepts for Clinic, Practitioner, Service, FAQ, and Policy, with explicit tenant_id, approval state, provenance, and freshness. Keep private patient/booking records in the existing access-controlled database.
3. Validate imports and preserve stable concept IDs as source references. Reject cross-tenant relationships. Import only allowlisted, approved fields into the existing KbEntries shape through tenant-scoped accessors; do not send raw Markdown instructions to the responder.
4. Use the existing embedding/retrieval path. Keep booking availability and transactional facts live in [booking](booking.md), rather than freezing them into wiki files.
5. Measure against a frozen multilingual set: expected source in top three, supported answer, rejection of unsupported claims, stale/unapproved content exclusion, cross-tenant leakage, and safe [handoff](handoff.md). Agree thresholds before implementation and compare with the current baseline.

# Owner inputs for our next session
- First pilot clinic and approver.
- Approved, non-patient FAQ source material.
- Which unanswered questions are currently most costly or frequent.

# Decision gate
Only add graph-aware traversal if linked relationships improve measured retrieval beyond the existing hybrid search. Capture results in [release evidence](release-evidence.md); graph adoption alone does not establish readiness.

# Source references
[^s1]: [app/kb/retrieval.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/kb/retrieval.py)
[^s2]: [app/models/collections.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/app/models/collections.py)
[^s3]: [tests/test_grounding_retrieval_acceptance.py](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/tests/test_grounding_retrieval_acceptance.py)

# Working-tree reconciliation
The source fingerprint includes the concurrent Tenants.update_settings addition. This does not implement the proposed OKF import or clinic approval workflow.
