# Vaani project knowledge

Start with [the knowledge index](docs/knowledge/index.md), then read only concepts relevant to the task. Follow references to current source code before editing. These draft summaries support navigation; they do not supersede code, authorization, or the production remediation ledger.

When changing a covered subsystem, update its concept with the same change. Run `python ops/knowledge.py check` to identify stale source snapshots and broken graph links. Review changed source and revise the prose before running `python ops/knowledge.py refresh CONCEPT_ID`; refresh is not human verification. Run the check again and inspect the diff.

Keep credentials, patient data, conversation transcripts, and tenant-specific private records out of this bundle. Engineering knowledge is separate from approved clinic-facing retrieval content. Distinguish planned behavior, implementation, recorded test results, and final acceptance. Use `docs/production-remediation-plan.md` for release status and closure requirements.

## Concurrent production remediation

Knowledge maintenance is advisory while another agent executes the production remediation plan. Continue the remediation acceptance checks and work order; knowledge drift is not a release blocker. The knowledge-curation task owns updates under docs/knowledge during this overlap. Leave stale fingerprints visible until that curator reviews the changed sources; do not bulk-refresh them to silence a warning. Keep changes to application code and the remediation ledger in the remediation task.
