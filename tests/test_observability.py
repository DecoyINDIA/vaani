"""Tests for structured JSON logging, correlation IDs, and Sentry scrubbing (W2-05)."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from app.config import settings
from app.observability import (
    JsonFormatter,
    _scrub,
    bind,
    clear,
    init_observability,
)


@pytest.fixture(autouse=True)
def clean_observability_context() -> None:
    clear()


def test_json_formatter_keys_and_output() -> None:
    formatter = JsonFormatter(service="api")
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Service started on port %d",
        args=(8000,),
        exc_info=None,
    )
    raw = formatter.format(record)
    data = json.loads(raw)

    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["msg"] == "Service started on port 8000"
    assert data["service"] == "api"
    assert "ts" in data
    assert data["ts"].endswith("Z")
    assert "tenant_id" not in data
    assert "conversation_id" not in data
    assert "message_id" not in data
    assert "exc_type" not in data


def test_context_ids_bind_and_clear() -> None:
    formatter = JsonFormatter(service="worker")
    record = logging.LogRecord(
        name="worker.inbound",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="Processing message",
        args=(),
        exc_info=None,
    )

    # Initially empty
    raw_before = formatter.format(record)
    assert "tenant_id" not in json.loads(raw_before)

    # Bind IDs
    bind(tenant_id="t_alpha", conversation_id="c_beta", message_id="m_gamma")
    raw_bound = formatter.format(record)
    data_bound = json.loads(raw_bound)
    assert data_bound["tenant_id"] == "t_alpha"
    assert data_bound["conversation_id"] == "c_beta"
    assert data_bound["message_id"] == "m_gamma"

    # Partial bind update
    bind(conversation_id="c_updated")
    data_updated = json.loads(formatter.format(record))
    assert data_updated["tenant_id"] == "t_alpha"
    assert data_updated["conversation_id"] == "c_updated"
    assert data_updated["message_id"] == "m_gamma"

    # Clear resets all three
    clear()
    data_cleared = json.loads(formatter.format(record))
    assert "tenant_id" not in data_cleared
    assert "conversation_id" not in data_cleared
    assert "message_id" not in data_cleared


def test_json_formatter_records_exc_type() -> None:
    formatter = JsonFormatter(service="api")
    try:
        raise ValueError("Something broke")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="api.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=30,
        msg="Unhandled failure",
        args=(),
        exc_info=exc_info,
    )
    raw = formatter.format(record)
    data = json.loads(raw)
    assert data["exc_type"] == "ValueError"
    assert data["msg"] == "Unhandled failure"


def test_scrub_removes_request_data_headers_cookies_and_frame_vars() -> None:
    event: dict[str, Any] = {
        "request": {
            "data": {"secret_token": "abc", "phone": "919999999999"},
            "cookies": {"session": "xyz"},
            "headers": {"Authorization": "Bearer secret"},
            "url": "https://api.example.com/v1/webhook",
        },
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "Database connection lost",
                    "stacktrace": {
                        "frames": [
                            {"function": "query", "vars": {"patient_name": "Ramesh", "query": "SELECT ..."}},
                            {"function": "handle", "vars": {"auth_token": "token123"}},
                        ]
                    },
                }
            ]
        },
        "threads": {
            "values": [
                {
                    "id": 1,
                    "stacktrace": {
                        "frames": [
                            {"function": "worker_loop", "vars": {"wa_id": "919876543210"}}
                        ]
                    },
                }
            ]
        },
        "tags": {"env": "prod"},
    }

    bind(tenant_id="tenant_scrub", conversation_id="conv_scrub", message_id="msg_scrub")
    result = _scrub(event, {})
    assert result is not None

    # Request data, cookies, headers must be purged
    assert "data" not in result["request"]
    assert "cookies" not in result["request"]
    assert "headers" not in result["request"]
    assert result["request"]["url"] == "https://api.example.com/v1/webhook"

    # Frame local variables must be deleted
    for frame in result["exception"]["values"][0]["stacktrace"]["frames"]:
        assert "vars" not in frame
    for frame in result["threads"]["values"][0]["stacktrace"]["frames"]:
        assert "vars" not in frame

    # Correlation tags added
    assert result["tags"]["tenant_id"] == "tenant_scrub"
    assert result["tags"]["conversation_id"] == "conv_scrub"
    assert result["tags"]["message_id"] == "msg_scrub"
    assert result["tags"]["env"] == "prod"


def test_init_observability_empty_dsn_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sentry_dsn", "")
    # Safe to call multiple times without error
    init_observability("api")
    init_observability("api")

    root = logging.getLogger()
    assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)


def test_log_call_with_phone_like_argument_not_altered() -> None:
    """Document: scrubbing log arguments is out of scope — prevention is by not logging them."""
    formatter = JsonFormatter(service="test")
    record = logging.LogRecord(
        name="test.raw",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Contact phone is %s",
        args=("919999999999",),
        exc_info=None,
    )
    raw = formatter.format(record)
    data = json.loads(raw)
    assert data["msg"] == "Contact phone is 919999999999"
