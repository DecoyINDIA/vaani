from __future__ import annotations

from app.agent.render import strip_citations


def test_strip_citations_single() -> None:
    assert strip_citations("Fee is Rs 500. [source_ref: faq_fees]") == "Fee is Rs 500."


def test_strip_citations_multiple() -> None:
    text = "Fee is Rs 500. [source_ref: faq_fees] Hours 9-5. [source_ref: faq_hours]"
    assert strip_citations(text) == "Fee is Rs 500. Hours 9-5."


def test_strip_citations_tag_only() -> None:
    assert strip_citations("[source_ref: faq_fees]") == ""


def test_strip_citations_hindi() -> None:
    assert strip_citations("फीस ₹500 है। [source_ref: faq_fees]") == "फीस ₹500 है।"


def test_strip_citations_odia() -> None:
    assert strip_citations("ଫିସ୍ ୫୦୦ ଟଙ୍କା। [source_ref: faq_fees]") == "ଫିସ୍ ୫୦୦ ଟଙ୍କା।"


def test_strip_citations_unclosed() -> None:
    assert strip_citations("Fee is Rs 500 [source_ref: faq_fees") == "Fee is Rs 500 [source_ref: faq_fees"


def test_strip_citations_empty_and_none() -> None:
    assert strip_citations("") == ""
    assert strip_citations(None) == ""


def test_strip_citations_mid_sentence() -> None:
    assert strip_citations("Fee [source_ref: faq_fees] is Rs 500.") == "Fee is Rs 500."


def test_strip_citations_case_insensitive() -> None:
    assert strip_citations("Fee is Rs 500. [SOURCE_REF: faq_fees]") == "Fee is Rs 500."


def test_strip_citations_preserves_newlines() -> None:
    assert strip_citations("Hello\n[source_ref: test]\nWorld") == "Hello\nWorld"
