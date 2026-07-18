# Static reply templates

Canned, **non-LLM** replies used where the responder node is unreachable by graph
topology (06-engineering-plan §0, rule 3). Maintained in all four languages —
respectful register only (आप / ଆପଣ; never तू/tum in system copy, TRD §4.3).

One file per template per language: `<template>.<lang>.md`, lang ∈ `hi | en | hi-Latn | or`.

Required set (TRD §4.1, §5.3):
- `out_of_scope` — static refusal + capability menu
- `medical_refusal` — templated refusal + booking offer + escalate flag
- `de_escalation` — one attempt before escalate (complaint/abuse)
- `location_landmark` — location pin + landmark-based directions

**Rule:** anything user-facing exists in all 4 languages or it does not ship
(06-engineering-plan §4, global definition of done).
