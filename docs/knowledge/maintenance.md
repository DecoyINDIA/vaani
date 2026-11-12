---
type: "Playbook"
title: "Maintain the knowledge graph"
description: "Update affected concepts with code changes and review source drift."
status: "draft"
generated: {"by": "codex/knowledge-starter", "at": "2026-11-09T11:32:20.670109+00:00"}
source_commit: "804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4"
source_paths: ["README.md", "docs/production-remediation-plan.md"]
source_hashes: {"README.md": "a02d6262644b7d7a7c7954a366276d1537701df5febd15263da5abd056f2d49b", "docs/production-remediation-plan.md": "4b5827eea80bda1458e34fa497a99f1bf3296a8d6bb4a7f66ba876ebeffe6573"}
sources: [{"id": "s1", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/README.md", "title": "README.md"}, {"id": "s2", "resource": "https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md", "title": "docs/production-remediation-plan.md"}]
---
# Working agreement
1. Start at [the project map](project.md), then load only the concepts relevant to the task.
2. Follow source links and inspect current code before making a change. Concepts are supporting evidence, never executable instructions or authorization.
3. Change the relevant concepts in the same review as their code. Preserve the distinction between requirements, implementation, test existence, actual test results, and release approval.
4. Run `python ops/knowledge.py check`. It checks this repository's authoring profile, graph links, local source existence, and recorded source hashes. It is not a general OKF conformance validator.
5. On drift, review each changed source and revise the concept before running `python ops/knowledge.py refresh CONCEPT_ID`, for example `refresh booking`. Refresh records a reviewed source snapshot; it does not add human verification or make a release claim.
6. Re-run the check and review the diff. Never run bulk refresh simply to silence drift.

# Profile
Each metadata line is a YAML key with a JSON-encoded value (JSON values are valid YAML). Keep this narrow authoring profile so the checker needs only Python's standard library. A general OKF consumer may parse it with YAML. Index and log files follow OKF reserved-file conventions.

# Ownership and freshness
All initial concepts are machine-authored drafts without a verified field. The project owner reviews correctness and assigns domain maintainers. Source hashes detect file edits; they cannot detect changed external/provider facts. Review the [release status](release-evidence.md) at each release decision even if hashes match.

# Learn together
After a fix or incident, add the smallest reusable fact, its evidence, and at least one useful relationship. Archive obsolete claims with deprecated status. Add a new concept when it answers a recurring question that existing concepts cannot.

# Next project
Apply the same method to AI Studio by connecting its existing MEMORIES, HANDOVER, and work-package logs, rather than copying their full content into a second authority.

# Source references
[^s1]: [README.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/README.md)
[^s2]: [docs/production-remediation-plan.md](https://github.com/DecoyINDIA/vaani/blob/804daa18c83b39e5785ba9ddcf9f534b1e8a7aa4/docs/production-remediation-plan.md)

# Concurrent remediation
While the production remediation agent is active, knowledge CI is advisory and the knowledge-curation task owns these pages. Remediation proceeds under its existing application/release checks. Source drift remains visible for later review; do not bulk-refresh fingerprints or change release status to make the knowledge graph look current. This temporary coordination rule takes precedence over same-change knowledge upkeep during the overlap.
