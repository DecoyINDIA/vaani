from __future__ import annotations

from app.agent.nodes.output_gate import output_gate


def state(response: str) -> dict:
    return {
        "intent": "faq_fees",
        "lang": "en",
        "response": response,
        "tool_results": [
            {
                "tool": "kb_search",
                "result": [
                    {"question": "Fee?", "answer": "Rs 500", "source_ref": "faq_fees"}
                ],
            }
        ],
    }


async def test_output_gate_rejects_invented_source() -> None:
    result = await output_gate(state("The fee is Rs 500. [source_ref: invented]"))
    assert result["regenerate"] is True


async def test_output_gate_rejects_altered_number_with_valid_source() -> None:
    result = await output_gate(state("The fee is Rs 700. [source_ref: faq_fees]"))
    assert result["regenerate"] is True


async def test_output_gate_accepts_grounded_number() -> None:
    result = await output_gate(state("The fee is Rs 500. [source_ref: faq_fees]"))
    assert result == {"regenerate": False}
