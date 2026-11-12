### TASK ID: W1-01

**Title:** Strip internal citation tags from every patient-facing message

**Priority:** P0

**Objective:** No text sent to a patient (WhatsApp or voice) and no stored outbound message contains `[source_ref: …]`.

**Why This Matters:** The responder is instructed to append citation tags so the output gate can verify grounding. Nothing removes them afterwards, so a patient would read "The fee is Rs 500. [source_ref: faq_fees]".

**Prerequisites:** None.

**Repository Context:**
- `app/agent/nodes/responder.py:108` tells the model to cite `[source_ref: key]`.
- `app/agent/nodes/output_gate.py` validates the tags; it must keep seeing them.
- `app/workers/inbound.py`: `response = result.get("response", "")` (≈ line 516) is sent unchanged by `send_freeform(...)` (≈ line 657) and stored as the outbound message (≈ line 677-690).
- `app/channels/voice/session.py` ≈ line 246: `response_text = res.get("response", "")` after `app.ainvoke(state)`.
- Constraint: stripping happens **after** the graph returns, never inside the graph.

**Files to Inspect:** `app/workers/inbound.py`, `app/channels/voice/session.py`, `app/agent/nodes/output_gate.py`, `tests/test_output_grounding.py`, `tests/test_inbound_loop.py`

**Files to Modify/Create:**
- Create `app/agent/render.py` — sanitizer.
- Modify `app/workers/inbound.py` — apply sanitizer once, right after reading `response` from the graph result.
- Modify `app/channels/voice/session.py` — apply sanitizer to `response_text` right after the graph call.
- Create `tests/test_render.py`; extend `tests/test_inbound_loop.py` with one assertion.

**Detailed Implementation Instructions:**
1. Create `app/agent/render.py` with `strip_citations(text: str) -> str` as specified below.
2. In `inbound.py::process_event`, replace `response = result.get("response", "")` with `response = strip_citations(result.get("response", ""))`. Every later use of `response` (send, stored message, audit) then uses the clean text. Do not touch the `intent == ...` branches that overwrite `response` with fixed strings.
3. In `voice/session.py`, wrap the graph response the same way at the single point where it is read from the graph result.
4. Add tests.

**Interfaces & Data Contracts:**
```python
def strip_citations(text: str) -> str:
    """Remove every '[source_ref: ...]' tag and tidy leftover whitespace."""
```
Rules: remove matches of `\s*\[source_ref:[^\]]*\]` case-insensitively; collapse runs of spaces/tabs to one space; remove a space left before `. , ! ? ।`; preserve newlines; `strip()` the result; empty or `None`-like input returns `""`.

**Algorithm / Pseudocode:**
```python
_TAG = re.compile(r"\s*\[source_ref:[^\]]*\]", re.IGNORECASE)
out = _TAG.sub("", text or "")
out = re.sub(r"[ \t]{2,}", " ", out)
out = re.sub(r" +([.,!?।])", r"\1", out)
return out.strip()
```

**Edge Cases:** multiple tags; tag at start; tag mid-sentence; unclosed `[source_ref: x` (leave as is); Devanagari/Odia text around the tag; text consisting only of a tag → `""` (the existing "empty response" branch in `inbound.py` then logs and sends nothing — acceptable).

**Non-Goals:** Do not change the responder prompt, the output gate, the mock LLM, or `send_freeform`. Do not strip other bracketed text.

**Acceptance Criteria:**
- `strip_citations("Fee is Rs 500. [source_ref: faq_fees]") == "Fee is Rs 500."`
- An inbound FAQ message processed through `process_event` under mocks produces an outbound message whose stored `text` has no `[source_ref`.
- All existing tests pass unchanged.

**Verification:**
```bash
uv run pytest -q tests/test_render.py tests/test_inbound_loop.py tests/test_output_grounding.py
uv run ruff check . && uv run mypy app && uv run pytest -q
grep -rn "strip_citations" app
```
The grep must show `render.py`, `inbound.py`, `voice/session.py`.

**Risk & Rollback:** Low. An existing test may assert a mock reply including the tag at the send boundary; update that assertion to the stripped text. Rollback = revert the commit.

**Effort & Complexity:** Small effort, low reasoning.

**Recommended Agent Tier:** Small agent

**Escalation Conditions:** `voice/session.py` does not read the graph response in one place, or more than three existing tests assert tagged outbound text.

**Standalone Execution Prompt:**
```
You are implementing task W1-01 in the Vaani repository. Read 07-AGENT_CONTEXT.md first.
Goal: patients must never see "[source_ref: ...]" tags.
1. Create app/agent/render.py with strip_citations(text: str) -> str: remove regex
   \s*\[source_ref:[^\]]*\] (case-insensitive), collapse repeated spaces, remove a space before
   . , ! ? ।, keep newlines, strip ends, return "" for empty input.
2. In app/workers/inbound.py process_event, change
   response = result.get("response", "")  to  response = strip_citations(result.get("response", "")).
3. In app/channels/voice/session.py, apply strip_citations where the graph result's "response"
   is read (near the build_graph()/ainvoke call).
4. Add tests/test_render.py (single tag, multiple tags, tag only, Hindi text, unclosed tag) and
   one assertion in tests/test_inbound_loop.py that the stored outbound text has no "[source_ref".
Do NOT edit responder.py, output_gate.py, llm.py or whatsapp.py.
Run: uv run ruff check . && uv run mypy app && uv run pytest -q
Stop and report if session.py reads the response in several places or >3 existing tests break.
Reply using the "Mandatory return format" in 07-AGENT_CONTEXT.md.
```
