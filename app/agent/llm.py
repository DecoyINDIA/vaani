from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def get_mock_response(prompt: str, model: str) -> str:
    """Provide rule-based responses to allow offline tests to pass without API keys."""
    # Split user prompt and system prompt
    parts = prompt.split(" ---SYSTEM_PROMPT--- ")
    user_prompt = parts[0]
    system_prompt = parts[1] if len(parts) > 1 else ""

    user_prompt_lower = user_prompt.lower()
    system_prompt_lower = system_prompt.lower()

    # Scope keyword matching to the actual user message when the calling prompt
    # wraps it — otherwise boilerplate like "Language detected: hi" pollutes
    # keyword checks (e.g. "hi" matching the greet branch).
    msg_match = re.search(
        r"(?:user message|customer latest message): '(.*)'", user_prompt_lower, re.DOTALL
    )
    if msg_match:
        user_prompt_lower = msg_match.group(1)

    is_classification = "intent" in system_prompt_lower or "classify" in system_prompt_lower

    if is_classification:
        # Prioritize safety and special gate intents first
        if any(w in user_prompt_lower for w in [
            "medical", "sar dard", "dard", "pain", "hurt", "treatment", "medic", "tablet",
            "dawai", "दर्द", "दवा", "ଯନ୍ତ୍ରଣା", "ଔଷଧ"
        ]):
            return '{"intent": "restricted_advice", "confidence": 0.98}'
        if any(w in user_prompt_lower for w in ["abuse", "stupid", "idiot", "nonsense"]):
            return '{"intent": "abuse", "confidence": 0.95}'
        if "complaint" in user_prompt_lower:
            return '{"intent": "complaint", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["human", "staff", "receptionist", "escalate"]):
            return '{"intent": "human_request", "confidence": 0.95}'

        # Appointment-mutation intents must be checked BEFORE "book": phrases like
        # "cancel my appointment" contain booking keywords too.
        if any(w in user_prompt_lower for w in ["reschedule", "change", "badal"]):
            return '{"intent": "reschedule", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["cancel", "radd", "रद्द", "ବାତିଲ"]):
            return '{"intent": "cancel", "confidence": 0.95}'
        if "status" in user_prompt_lower:
            return '{"intent": "booking_status", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["payment", "deposit", "razorpay"]):
            return '{"intent": "payment_query", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in [
            "appointment", "booking", "book", "milna", "ଦେଖା କରିବି", "अपॉइंटमेंट", "बुक"
        ]):
            return '{"intent": "book", "confidence": 0.95}'

        # FAQs
        if any(w in user_prompt_lower for w in ["timing", "timings", "hours", "open", "समय", "खुल", "ସମୟ"]):
            return '{"intent": "faq_hours", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["fee", "fees", "charge", "consultation", "शुल्क", "फीस", "ଫିସ୍"]):
            return '{"intent": "faq_fees", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["location", "address", "rasta", "kahan", "map", "पता", "ଠିକଣା"]):
            return '{"intent": "faq_location", "confidence": 0.95}'
        if any(w in user_prompt_lower for w in ["doctor", "practitioner", "sharma"]):
            return '{"intent": "faq_staff", "confidence": 0.90}'

        # Greetings (use split to avoid matching substrings like "hi" inside "hai")
        user_words = [w.strip("'\"!?.,") for w in user_prompt_lower.split()]
        if any(w in user_words for w in ["hello", "hi", "namaste", "hey"]):
            return '{"intent": "greet", "confidence": 1.0}'

        return '{"intent": "out_of_scope", "confidence": 1.0}'

    # --- Grounded responder mock ---
    # Route on the source_refs present inside the Grounded Facts block ONLY.
    # The citation-rule boilerplate always mentions "fees, timings, address" and
    # example refs, so keyword-matching the whole system prompt misroutes every
    # intent to the hours answer.
    facts_match = re.search(
        r"Grounded Facts:\n(.*?)(?:\n\nStrict Citation Rule|\Z)", system_prompt, re.DOTALL
    )
    facts = facts_match.group(1) if facts_match else ""
    facts_lower = facts.lower()

    if "source_ref: slots_list" in facts_lower:
        slot_match = re.search(r"Available Slots[^\n]*", facts)
        slots_line = slot_match.group(0) if slot_match else "Available slots found"
        return f"{slots_line}. Kripya bataiye kaun sa samay aapke liye theek rahega. [source_ref: slots_list]"

    faq_responses = {
        "faq_fees": "The consultation fee is Rs 500. [source_ref: faq_fees]",
        "faq_hours": "We are open from 9:00 AM to 6:00 PM Monday through Saturday. [source_ref: faq_hours]",
        "faq_location": "We are located near Main Market, Bhubaneswar, opposite HDFC Bank. [source_ref: faq_location]",
    }
    faq_keywords = {
        "faq_fees": ["fee", "fees", "charge", "consultation", "शुल्क", "फीस", "ଫିସ୍"],
        "faq_hours": ["timing", "hours", "open", "समय", "खुल", "ସମୟ"],
        "faq_location": ["location", "address", "rasta", "kahan", "map", "पता", "ଠିକଣା"],
    }
    # Prefer the FAQ fact that matches the user's question; kb_search can return
    # several entries, so refs alone are ambiguous.
    for ref, keywords in faq_keywords.items():
        if f"source_ref: {ref}" in facts_lower and any(w in user_prompt_lower for w in keywords):
            return faq_responses[ref]
    for ref, response in faq_responses.items():
        if f"source_ref: {ref}" in facts_lower:
            return response

    user_words = [w.strip("'\"!?.,") for w in user_prompt_lower.split()]
    if any(w in user_words for w in ["hello", "hi", "namaste", "hey"]):
        return "Namaste! How can I help you today?"

    return "I'm sorry, I couldn't find information about that. I will escalate this to our team to help you. [source_ref: fallback]"


class LlmError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class LlmTimeoutError(LlmError, httpx.ReadTimeout):
    def __init__(self, message: str) -> None:
        LlmError.__init__(self, message, retryable=True)
        httpx.ReadTimeout.__init__(self, message)


_http: httpx.AsyncClient | None = None


def set_http_client(client: httpx.AsyncClient | None) -> None:
    """Set or reset the shared HTTP client (used for tests and lifecycle)."""
    global _http
    _http = client


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or getattr(_http, "is_closed", False) or not isinstance(_http, httpx.AsyncClient):
        try:
            _http = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.llm_timeout_seconds, connect=3.0)
            )
        except TypeError:
            _http = httpx.AsyncClient()
    return _http


async def _record_call(
    tenant_id: str,
    node: str,
    model: str,
    latency_ms: int,
    prompt_tokens: int,
    completion_tokens: int,
    ok: bool,
    error_type: str | None,
) -> None:
    if not tenant_id:
        return
    try:
        from app.models.collections import LlmCalls
        doc = {
            "tenant_id": tenant_id,
            "node": node,
            "model": model,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "ok": ok,
            "error_type": error_type,
            "ts": datetime.now(UTC).replace(tzinfo=None),
        }
        await LlmCalls(tenant_id).insert_one(doc)
    except Exception as exc:
        logger.warning("Failed to record LLM telemetry: %s", exc)


async def call_openrouter(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 500,
    json_mode: bool = False,
) -> tuple[str, dict[str, int]]:
    """Perform one HTTP attempt against OpenRouter, returning (text, usage).

    Raises LlmError with retryable=True for timeouts, transport errors, HTTP 429, and >= 500.
    Raises LlmError with retryable=False for 4xx errors, empty choices, or malformed payloads.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DecoyINDIA/vaani",
        "X-Title": "Vaani Front Desk",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode and settings.llm_json_mode:
        payload["response_format"] = {"type": "json_object"}

    client = _client()
    try:
        resp = await client.post(url, headers=headers, json=payload)
    except (httpx.TimeoutException, httpx.ReadTimeout) as exc:
        raise LlmTimeoutError(
            f"Network error calling OpenRouter: {type(exc).__name__}"
        ) from exc
    except httpx.TransportError as exc:
        raise LlmError(
            f"Network error calling OpenRouter: {type(exc).__name__}", retryable=True
        ) from exc
    except Exception as exc:
        raise LlmError(
            f"Unexpected error calling OpenRouter: {type(exc).__name__}", retryable=False
        ) from exc

    if resp.status_code == 200:
        try:
            body = resp.json()
            choices = body.get("choices")
            if not choices:
                raise LlmError("OpenRouter returned empty choices", retryable=False)
            message = choices[0].get("message")
            if not message or message.get("content") is None:
                raise LlmError("OpenRouter choice missing message content", retryable=False)
            content = str(message["content"]).strip()
            raw_usage = body.get("usage") or {}
            usage = {
                "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
            }
            return content, usage
        except Exception as exc:
            if isinstance(exc, LlmError):
                raise
            raise LlmError(
                f"Malformed OpenRouter response body: {exc}", retryable=False
            ) from exc

    status = resp.status_code
    retryable = status == 429 or status >= 500
    raise LlmError(f"OpenRouter HTTP error {status}: {resp.text}", retryable=retryable)


async def query_llm(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 500,
    *,
    json_mode: bool = False,
    node: str = "",
    tenant_id: str = "",
) -> str:
    """Query OpenRouter, using the rule-based adapter only when explicitly enabled."""
    if settings.use_mock_adapters or settings.use_mock_llm:
        logger.debug("[LLM Mock] model=%s", model)
        return get_mock_response(prompt + " ---SYSTEM_PROMPT--- " + (system_prompt or ""), model)
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required when mock adapters are disabled")

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Attempt 1
    t0 = time.perf_counter()
    try:
        text, usage = await call_openrouter(
            model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await _record_call(
            tenant_id=tenant_id,
            node=node,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            ok=True,
            error_type=None,
        )
        return text
    except LlmError as err:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await _record_call(
            tenant_id=tenant_id,
            node=node,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            ok=False,
            error_type=type(err).__name__,
        )
        if not err.retryable:
            raise

    # Attempt 2 (fallback model or same model on retryable error)
    fallback_model = settings.llm_model_fallback_provider or model
    t0 = time.perf_counter()
    try:
        text, usage = await call_openrouter(
            fallback_model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await _record_call(
            tenant_id=tenant_id,
            node=node,
            model=fallback_model,
            latency_ms=latency_ms,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            ok=True,
            error_type=None,
        )
        return text
    except Exception as err:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await _record_call(
            tenant_id=tenant_id,
            node=node,
            model=fallback_model,
            latency_ms=latency_ms,
            prompt_tokens=0,
            completion_tokens=0,
            ok=False,
            error_type=type(err).__name__,
        )
        if isinstance(err, LlmTimeoutError):
            raise
        raise RuntimeError(f"OpenRouter query failed after fallback retry: {err}") from err
