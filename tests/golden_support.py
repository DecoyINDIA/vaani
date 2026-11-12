"""Golden transcript test support: Meta webhook payload builders and WhatsApp recorder."""

from __future__ import annotations

from typing import Any

import app.channels.whatsapp
import pytest


def make_text_payload(
    wa_id: str,
    text: str,
    msg_id: str,
    profile_name: str = "Test Patient",
) -> dict[str, Any]:
    """Build a Meta Cloud API inbound text webhook payload."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": wa_id,
                                    "profile": {"name": profile_name},
                                }
                            ],
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": wa_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def make_list_reply_payload(
    wa_id: str,
    slot_id: str,
    title: str,
    msg_id: str,
    profile_name: str = "Test Patient",
) -> dict[str, Any]:
    """Build a Meta Cloud API inbound list-reply webhook payload."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": wa_id,
                                    "profile": {"name": profile_name},
                                }
                            ],
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": wa_id,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {"id": slot_id, "title": title},
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def make_button_reply_payload(
    wa_id: str,
    button_id: str,
    title: str,
    msg_id: str,
    profile_name: str = "Test Patient",
) -> dict[str, Any]:
    """Build a Meta Cloud API inbound button-reply webhook payload."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": wa_id,
                                    "profile": {"name": profile_name},
                                }
                            ],
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": wa_id,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": button_id, "title": title},
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def make_media_payload(
    wa_id: str,
    media_type: str,
    msg_id: str,
    profile_name: str = "Test Patient",
) -> dict[str, Any]:
    """Build a Meta Cloud API inbound media webhook payload."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": wa_id,
                                    "profile": {"name": profile_name},
                                }
                            ],
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": wa_id,
                                    "type": media_type,
                                    media_type: {"id": f"media_{msg_id}"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


class WhatsAppRecorder:
    """Records all calls made to app.channels.whatsapp._post."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def record(self, to: str, body: dict[str, Any], operation_key: str) -> None:
        self.messages.append({"to": to, "body": body, "operation_key": operation_key})

    def clear(self) -> None:
        self.messages.clear()


@pytest.fixture
def wa_recorder(monkeypatch: pytest.MonkeyPatch) -> WhatsAppRecorder:
    """Fixture wrapping app.channels.whatsapp._post to intercept outbound calls."""
    recorder = WhatsAppRecorder()
    orig_post = app.channels.whatsapp._post

    async def _recording_post(
        tenant_id: str, wa_id: str, body: dict[str, Any], operation_key: str
    ) -> dict[str, Any]:
        recorder.record(to=wa_id, body=body, operation_key=operation_key)
        return await orig_post(tenant_id, wa_id, body, operation_key)

    monkeypatch.setattr(app.channels.whatsapp, "_post", _recording_post)
    return recorder
