# Prompts

Versioned, model-portable prompts — **one file per node per language** (TRD ADR-02).
No provider-specific features in core paths (OpenRouter is model-pinned but portable).

Naming: `<node>.<lang>.md` where lang ∈ `hi | en | hi-Latn | or`.
Example: `intent.hi.md`, `responder.en.md`.

**CI gate (06-engineering-plan §0, rule 4):** any change here fails CI unless
`evals/` passes — intent F1 ≥ threshold and hallucination incidents = 0. Prompt
changes carry an eval-report link in the PR.
