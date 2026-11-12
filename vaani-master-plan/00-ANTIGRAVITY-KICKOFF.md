# Antigravity kickoff - implement all written Waves 1 and 2

You are the sole implementation orchestrator for Vaani. Work continuously through every written Wave 1 and Wave 2 packet, including their integration checkpoints, without asking for routine choices already settled in the repository plan.

## Mission

Starting from the latest clean committed `main`, implement all packets in `vaani-master-plan/06-AGENT_TASKS/` in the exact dependency order defined by `vaani-master-plan/08-EXECUTION_ORCHESTRATOR.md`. Complete Wave 1 and INT-1, then Wave 2 and all locally executable INT-2 checks. Stop only for a genuine safety boundary that cannot be resolved from code, tests, or the recorded owner decisions.

## Preflight

1. Read `AGENTS.md`, `docs/knowledge/index.md`, `vaani-master-plan/07-AGENT_CONTEXT.md`, `vaani-master-plan/06-AGENT_TASKS/README.md`, `vaani-master-plan/08-EXECUTION_ORCHESTRATOR.md`, `vaani-master-plan/09-QUALITY_GATES.md`, and `docs/decision-log.md` completely.
2. Work directly on `main`; do not create a branch or worktree.
3. The concurrent remediation task must have finished and `git status --short` must be empty before implementation begins. Never discard, stash, overwrite, or automatically commit pre-existing work. If the tree is dirty, wait for that task to finish; this is the only kickoff precondition.
4. Record the starting commit, baseline test count, and mock-eval result.

## Execution order

Implement Wave 1 exactly as the orchestrator orders it. Because you are one agent on `main`, serialize the chains while preserving every within-chain dependency. After all 13 packets pass their task gates, run and record INT-1.

Then implement Wave 2 in this order:

1. W2-04
2. W2-05
3. W2-02
4. W2-01
5. W2-03
6. W2-08
7. W2-09
8. W2-06
9. W2-07
10. INT-2 checks that can run without external credentials or human sign-off

Before each packet, reconcile its Repository Context against the code produced by earlier packets. Locate symbols rather than trusting line numbers. If a premise moved, update the packet minimally, record the correction in `docs/decision-log.md`, and continue. Do not work around a false premise silently.

## Per-packet loop

For every packet:

1. Read the whole packet and only the knowledge concepts relevant to the subsystem.
2. Inspect current symbols, tests, and any prior packet changes.
3. Implement the smallest change satisfying every acceptance criterion. Preserve tenant isolation, idempotency, safety routing, PII rules, and mock-LLM compatibility.
4. Add or update the packet's tests. Never weaken security, tenant, booking-race, or delivery assertions.
5. Run the focused tests, then the full task gate in `09-QUALITY_GATES.md`. Run the dashboard gate when applicable. Run the packet's independent review checklist where required and fix findings before proceeding.
6. Update the relevant source-backed knowledge concept when the subsystem is covered. Follow `AGENTS.md`: run `python ops/knowledge.py check`, revise prose after reviewing changed source, do not bulk-refresh fingerprints owned by the concurrent curator, and inspect the diff.
7. Stage only files owned by the packet plus its tests, permitted knowledge updates, and decision evidence. Commit once with the packet ID in the subject. Never use destructive Git commands.
8. Append the packet's mandatory completion report, exact commands, counts, commit SHA, deviations, and remaining external gates to `docs/decision-log.md`.
9. Continue immediately to the next packet.

If a check fails, diagnose and fix it. Two failed approaches to the same problem require a fresh reread of the packet and current source, not abandonment. A failure unrelated to the packet must be documented and isolated; do not hide it or weaken a test. Keep progressing on any independent work while a non-code external gate is unavailable.

## Recorded owner decisions

- Implement all written Wave 1 and Wave 2 packets. Do not invent Wave 3 or Wave 4 packets.
- `sentry-sdk>=2` is approved. Target Sentry's free Developer plan. Initialize it only when `SENTRY_DSN` exists, disable tracing, set `send_default_pii=False`, scrub PII, and never log message text, phone numbers, tokens, or patient data.
- The real-model thresholds in `09-QUALITY_GATES.md` section 5 are approved.
- Do not prescribe, document, or hardcode a candidate model identifier. Choose no model on the owner's behalf.
- No OpenRouter or other hosted-model credential is available for this run. Never request a secret in chat, print one, commit one, or invent one.
- Build W2-02's real-model harness, dataset, and workflow and test them with injected fakes. Do not run or claim a credentialed evaluation.
- Implement W2-03 after W2-02's harness exists and complete its offline gates and independent review. Record its before/after real-model reports as pending external acceptance.
- Missing model credentials must not pause code implementation, but W2-02's real run, W2-03's real comparison, INT-2, and pilot readiness must remain clearly incomplete.
- Implement Hindi/Odia copy and the synthetic dataset now. Keep both marked unreviewed until human review after implementation; they cannot support pilot approval before sign-off.

## Boundaries

- Follow current code and `AGENTS.md` over planning prose when they conflict. Record the conflict and the resolution.
- Do not modify frozen areas unless the active packet names them.
- Do not add dependencies except those explicitly authorized by a packet or the recorded Sentry approval.
- Do not access or include credentials, patient data, tenant-private records, or real conversation transcripts.
- Do not claim external evidence you did not observe. Distinguish implemented code, recorded tests, pending human review, pending credentialed evaluation, and final acceptance.
- Do not deploy, contact providers, create paid services, or run live patient traffic.
- Multiple worker replicas remain unsupported unless a later approved packet explicitly adds distributed ordering. W2-06 provides concurrency inside one process only.

## Completion

Finish only when every written packet has an implementation commit and reproduced local gate, INT-1 is recorded, all locally executable INT-2 checks are recorded, and every unavailable external acceptance item is listed plainly. Return one final report containing:

- packet-to-commit map;
- files and migrations added;
- exact test, lint, type, build, eval, and review results;
- INT-1 and local INT-2 evidence;
- pending credentialed model evaluation and W2-03 comparison;
- pending Hindi/Odia and dataset review;
- any other blocker to pilot or production acceptance.

Do not describe pending external gates as implementation failures, and do not describe completed implementation as pilot readiness.
