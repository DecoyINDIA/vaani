# Decision log

## 12 November 2026 - Waves 1-2 execution authority

- Scope: implement every written Wave 1 packet, pass INT-1, then implement every written Wave 2 packet and attempt INT-2. Unwritten Wave 3-4 work is out of scope.
- Integration: work directly on `main`, one packet per commit, after the concurrent remediation task leaves a clean working tree. No task branches or worktrees.
- Observability: adding `sentry-sdk>=2` is approved. Use Sentry's free Developer plan, disable tracing, set `send_default_pii=False`, and apply the packet's scrubber. A missing Sentry DSN does not block implementation.
- Evaluation: the thresholds in `vaani-master-plan/09-QUALITY_GATES.md` section 5 are ratified.
- Models and credentials: no candidate model identifiers are prescribed or recorded, and no OpenRouter credential is available. Do not hardcode a model choice. Complete provider-facing code and offline tests, but record credentialed W2-02 execution, W2-03 before/after reports, INT-2, and pilot readiness as pending external acceptance.
- Human review: implement Hindi/Odia strings and the synthetic evaluation dataset now. Native-speaker and dataset review happens afterward and remains mandatory before the pilot.

This decision separates implementation completion from external acceptance. Missing credentials or reviewers do not justify claiming a gate passed, but they do not pause independent code work.
