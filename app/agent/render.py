from __future__ import annotations

import re

_TAG = re.compile(r"\s*\[source_ref:[^\]]*\]", re.IGNORECASE)


def strip_citations(text: str | None) -> str:
    """Remove every '[source_ref: ...]' tag and tidy leftover whitespace."""
    if not text:
        return ""
    out = _TAG.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([.,!?।])", r"\1", out)
    return out.strip()
