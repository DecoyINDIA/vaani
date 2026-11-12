"""Structured JSON logging with tenant/conversation context and Sentry error reporting (W2-05)."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

import sentry_sdk
from sentry_sdk.types import Event, Hint

from app.config import settings

_tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
_conversation_id_var: ContextVar[str] = ContextVar("conversation_id", default="")
_message_id_var: ContextVar[str] = ContextVar("message_id", default="")


def bind(
    *,
    tenant_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Bind contextual IDs to the current execution context."""
    if tenant_id is not None:
        _tenant_id_var.set(tenant_id)
    if conversation_id is not None:
        _conversation_id_var.set(conversation_id)
    if message_id is not None:
        _message_id_var.set(message_id)


def clear() -> None:
    """Clear all contextual IDs from the current execution context."""
    _tenant_id_var.set("")
    _conversation_id_var.set("")
    _message_id_var.set("")


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects with context tags."""

    def __init__(self, service: str = "api") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        ts_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        log_obj: dict[str, Any] = {
            "ts": ts_str,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": self.service,
        }
        tenant_id = _tenant_id_var.get()
        conversation_id = _conversation_id_var.get()
        message_id = _message_id_var.get()
        if tenant_id:
            log_obj["tenant_id"] = tenant_id
        if conversation_id:
            log_obj["conversation_id"] = conversation_id
        if message_id:
            log_obj["message_id"] = message_id
        if record.exc_info and record.exc_info[0]:
            log_obj["exc_type"] = record.exc_info[0].__name__

        return json.dumps(log_obj, ensure_ascii=False)


def _scrub(event: Event, hint: Hint) -> Event | None:
    """Scrub request body, headers, cookies, and local variables from Sentry events."""
    if "request" in event and isinstance(event["request"], dict):
        req = event["request"]
        req.pop("data", None)
        req.pop("cookies", None)
        req.pop("headers", None)

    if "exception" in event and isinstance(event["exception"], dict):
        for exc in event["exception"].get("values", []):
            stacktrace = exc.get("stacktrace")
            if stacktrace and isinstance(stacktrace, dict) and "frames" in stacktrace:
                for frame in stacktrace["frames"]:
                    frame.pop("vars", None)

    if "threads" in event and isinstance(event["threads"], dict):
        for thread in event["threads"].get("values", []):
            stacktrace = thread.get("stacktrace")
            if stacktrace and isinstance(stacktrace, dict) and "frames" in stacktrace:
                for frame in stacktrace["frames"]:
                    frame.pop("vars", None)

    tags = event.setdefault("tags", {})
    tenant_id = _tenant_id_var.get()
    conversation_id = _conversation_id_var.get()
    message_id = _message_id_var.get()
    if tenant_id:
        tags["tenant_id"] = tenant_id
    if conversation_id:
        tags["conversation_id"] = conversation_id
    if message_id:
        tags["message_id"] = message_id

    return event


def init_observability(service: str) -> None:
    """Configure root logger with JsonFormatter and initialize Sentry if configured."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service=service))
    root.addHandler(handler)

    if settings.sentry_dsn and not sentry_sdk.is_initialized():
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            send_default_pii=False,
            traces_sample_rate=0.0,
            before_send=_scrub,
        )
