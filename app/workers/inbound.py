"""Inbound worker — Redis Streams consumer (TRD §1, Week 3 task 3.3).

Consumer group; dead-letter after 3 retries. Kill mid-message -> reprocessed, not
lost. Pulls normalized inbound events, runs the agent graph, sends the reply
through app.channels + app.audit. Entrypoint: `python -m app.workers.inbound`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app import audit
from app.agent.graph import build_graph
from app.agent.render import strip_citations
from app.agent.tools.booking_cancel import booking_cancel
from app.agent.tools.booking_create import booking_create
from app.agent.tools.booking_move import booking_move
from app.booking.timefmt import format_local, tenant_timezone
from app.channels.whatsapp import (
    WindowClosedError,
    send_booking_confirmation,
    send_cancel_confirmation,
    send_freeform,
    send_slot_picker,
)
from app.config import settings
from app.gateway.middleware import get_redis
from app.i18n import normalize_lang, t
from app.models.base import mongo_id_candidates
from app.models.collections import Bookings, Contacts, Conversations, Messages, Slots, Tenants

logger = logging.getLogger(__name__)

STREAM = "vaani:inbound_stream"
DEAD_LETTER = "vaani:inbound_dlq"
GROUP = "vaani:workers"
CONSUMER = "worker-1"
MAX_DELIVERIES = 3  # dead-letter after 3 failed attempts (kill-safe reprocessing)
_IDLE_RECLAIM_MS = 60_000  # reclaim messages stalled longer than 60s

UNSUPPORTED_TYPES: frozenset[str] = frozenset(
    {"audio", "image", "video", "document", "sticker", "location", "contacts"}
)
UNSUPPORTED_REPLY = t("media.unsupported", "en")


def _render_slot_label(value: Any, tz: ZoneInfo, lang: str) -> str:
    """Format stored slot instant to localized label, or return unchanged if already formatted."""
    if not isinstance(value, str):
        return str(value)
    try:
        dt = datetime.fromisoformat(value)
        return format_local(dt, tz, lang=lang)
    except (ValueError, TypeError):
        return value


async def _conversation_lang(tenant_id: str, conversation_db_id: Any, contact_id: str) -> str:
    """Resolve active conversation language: conversation -> contact -> tenant -> 'en'."""
    try:
        conv = await Conversations(tenant_id).find_one({"_id": conversation_db_id})
        if conv and conv.get("lang"):
            return normalize_lang(conv["lang"])
    except Exception:
        pass

    try:
        contact = await Contacts(tenant_id).find_one(
            {"_id": {"$in": mongo_id_candidates(contact_id)}}
        )
        if contact and contact.get("lang_pref"):
            return normalize_lang(contact["lang_pref"])
    except Exception:
        pass

    try:
        tenant = await Tenants.find_by_id(tenant_id)
        if tenant and tenant.get("locale_default"):
            return normalize_lang(tenant["locale_default"])
    except Exception:
        pass

    return "en"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pull sender wa_id + text out of a Meta Cloud API webhook payload."""
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        msg = value["messages"][0]
    except (KeyError, IndexError):
        return None

    wa_id = msg.get("from") or (value.get("contacts") or [{}])[0].get("wa_id")
    if not wa_id:
        return None

    text = ""
    action_id = ""
    if msg.get("type") == "text":
        text = msg.get("text", {}).get("body", "")
    elif msg.get("type") == "interactive":
        interactive = msg.get("interactive", {})
        reply = interactive.get("list_reply") or interactive.get("button_reply") or {}
        action_id = str(reply.get("id", ""))
        text = str(reply.get("title", action_id))
    elif msg.get("type") == "button":
        button = msg.get("button", {})
        action_id = str(button.get("payload", ""))
        text = str(button.get("text", action_id))

    profile_name = ""
    contacts = value.get("contacts") or []
    if contacts:
        profile_name = contacts[0].get("profile", {}).get("name", "")

    return {
        "wa_id": wa_id,
        "text": text,
        "profile_name": profile_name,
        "action_id": action_id,
        "message_type": str(msg.get("type", "")),
    }


async def _resolve_conversation(
    tenant_id: str, wa_id: str, name: str
) -> tuple[str, str, Any, str]:
    """Upsert the contact (refresh 24h-window ts) and open/find its conversation."""
    contacts = Contacts(tenant_id)
    await contacts.update_one(
        {"wa_id": wa_id},
        {
            "$set": {"wa_id": wa_id, "last_inbound_ts": _now()},
            "$setOnInsert": {"name": name or wa_id, "created_at": _now()},
        },
        upsert=True,
    )
    contact = await contacts.find_one({"wa_id": wa_id})
    contact_id = str(contact["_id"]) if contact else wa_id

    conversations = Conversations(tenant_id)
    convo = await conversations.find_one(
        {
            "contact_id": {"$in": mongo_id_candidates(contact_id)},
            "state": {"$in": ["bot", "human", "open"]},
        }
    )
    if convo:
        state = "bot" if convo["state"] == "open" else str(convo["state"])
        update_fields: dict[str, Any] = {"last_msg_at": _now()}
        if convo["state"] == "open":
            update_fields["state"] = "bot"
        await conversations.update_one({"_id": convo["_id"]}, {"$set": update_fields})
        return str(convo["_id"]), state, convo["_id"], contact_id

    result = await conversations.insert_one(
        {
            "contact_id": contact_id,
            "channel": "wa",
            "state": "bot",
            "started_at": _now(),
            "last_msg_at": _now(),
        }
    )
    return str(result.inserted_id), "bot", result.inserted_id, contact_id


async def _store_inbound(
    tenant_id: str,
    conversation_id: str,
    text: str,
    message_id: str | None,
    *,
    action_id: str = "",
    intent: str | None = None,
    confidence: float | None = None,
    message_type: str | None = None,
) -> None:
    msg_type = message_type or ("interactive" if action_id else "text")
    document = {
        "conversation_id": conversation_id,
        "direction": "inbound",
        "type": msg_type,
        "text": text,
        "action_id": action_id or None,
        "intent": intent,
        "confidence": confidence,
        "ts": _now(),
    }
    if message_id:
        await Messages.upsert_message_unscoped(message_id, tenant_id, document)
    else:
        await Messages(tenant_id).insert_one(document)


async def _send_flow_text(
    tenant_id: str,
    wa_id: str,
    conversation_id: str,
    text: str,
    operation_key: str,
) -> None:
    result = await send_freeform(tenant_id, wa_id, text, operation_key=operation_key)
    await Messages(tenant_id).update_one(
        {"operation_key": operation_key},
        {
            "$setOnInsert": {
                "conversation_id": conversation_id,
                "direction": "outbound",
                "type": "text",
                "text": text,
                "operation_key": operation_key,
                "provider_message_id": result.get("messages", [{}])[0].get("id"),
                "ts": _now(),
            }
        },
        upsert=True,
    )


async def _record_flow_interactive(
    tenant_id: str,
    conversation_id: str,
    operation_key: str,
    flow: str,
    result: dict[str, Any],
) -> None:
    await Messages(tenant_id).update_one(
        {"operation_key": operation_key},
        {
            "$setOnInsert": {
                "conversation_id": conversation_id,
                "direction": "outbound",
                "type": "interactive",
                "flow": flow,
                "operation_key": operation_key,
                "provider_message_id": result.get("messages", [{}])[0].get("id"),
                "ts": _now(),
            }
        },
        upsert=True,
    )


async def _handle_cancel_action(
    *,
    tenant_id: str,
    wa_id: str,
    contact_id: str,
    conversation_id: str,
    conversation_db_id: Any,
    message_id: str | None,
    text: str,
    action_id: str,
) -> bool:
    if action_id not in {"cancel:confirm", "cancel:keep"}:
        return False
    conv = await Conversations(tenant_id).find_one({"_id": conversation_db_id})
    flow = (conv or {}).get("cancel_flow")
    if not isinstance(flow, dict) or flow.get("stage") != "awaiting_confirmation":
        return False

    await _store_inbound(tenant_id, conversation_id, text, message_id, action_id=action_id)
    created_at = flow.get("created_at")
    expired = False
    if isinstance(created_at, datetime):
        expired = _now() - created_at > timedelta(minutes=30)

    lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)

    if action_id == "cancel:keep" or expired:
        await Conversations(tenant_id).update_one(
            {"_id": conversation_db_id, "state": "bot"},
            {"$unset": {"cancel_flow": ""}},
        )
        await _send_flow_text(
            tenant_id=tenant_id,
            wa_id=wa_id,
            conversation_id=conversation_id,
            text=t("cancel.kept", lang),
            operation_key=f"cancel-keep:{message_id or conversation_id}",
        )
        return True

    booking_id = str(flow.get("booking_id", ""))
    when = str(flow.get("when", "your appointment"))
    result = await booking_cancel(tenant_id, booking_id, contact_id=contact_id)
    await Conversations(tenant_id).update_one(
        {"_id": conversation_db_id, "state": "bot"},
        {"$set": {"cancel_flow.stage": "completed"}},
    )
    if result.get("status") == "success":
        reply_text = t("cancel.done", lang, when=when)
    else:
        reply_text = t("cancel.failed", lang)
    await _send_flow_text(
        tenant_id=tenant_id,
        wa_id=wa_id,
        conversation_id=conversation_id,
        text=reply_text,
        operation_key=f"cancel-result:{conversation_id}:{booking_id}",
    )
    return True


async def _handle_booking_action(
    *,
    tenant_id: str,
    wa_id: str,
    contact_id: str,
    conversation_id: str,
    conversation_db_id: Any,
    message_id: str | None,
    text: str,
    action_id: str,
) -> bool:
    conversation = await Conversations(tenant_id).find_one({"_id": conversation_db_id})
    flow = conversation.get("booking_flow") if conversation else None
    if not isinstance(flow, dict) or not action_id:
        return False

    tenant = await Tenants.find_by_id(tenant_id)
    tenant_tz = tenant_timezone(tenant)
    lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)

    if action_id.startswith("slot:") and flow.get("stage") == "choose_slot":
        slot_id = action_id.removeprefix("slot:")
        slots = flow.get("slots", {})
        selected = slots.get(slot_id) if isinstance(slots, dict) else None
        if not isinstance(selected, str):
            await _store_inbound(
                tenant_id, conversation_id, text, message_id, action_id=action_id
            )
            await _send_flow_text(
                tenant_id,
                wa_id,
                conversation_id,
                t("booking.stale_selection", lang),
                f"booking-stale:{message_id or conversation_id}",
            )
            return True
        updated_flow = {**flow, "stage": "awaiting_confirmation", "slot_id": slot_id}
        await Conversations(tenant_id).update_one(
            {"_id": conversation_db_id, "state": "bot"},
            {"$set": {"booking_flow": updated_flow}},
        )
        await _store_inbound(
            tenant_id, conversation_id, text, message_id, action_id=action_id
        )
        confirmation_key = f"booking-confirm-picker:{conversation_id}:{slot_id}"
        when_str = _render_slot_label(selected, tenant_tz, lang)
        confirmation_prompt = t(
            "booking.confirm_prompt",
            lang,
            service=flow.get("service", "Consultation"),
            practitioner=flow.get("practitioner_name") or "our team",
            when=when_str,
        )
        confirmation = await send_booking_confirmation(
            tenant_id,
            wa_id,
            prompt=confirmation_prompt,
            operation_key=confirmation_key,
            confirm_title=t("ui.confirm", lang),
            again_title=t("ui.choose_again", lang),
        )
        await _record_flow_interactive(
            tenant_id,
            conversation_id,
            confirmation_key,
            "booking_confirmation",
            confirmation,
        )
        return True

    if action_id == "booking:cancel":
        slots = flow.get("slots", {})
        picker_slots = [
            {"slot_id": str(s_id), "label": _render_slot_label(label, tenant_tz, lang)}
            for s_id, label in slots.items()
        ] if isinstance(slots, dict) else []
        await Conversations(tenant_id).update_one(
            {"_id": conversation_db_id, "state": "bot"},
            {"$set": {"booking_flow.stage": "choose_slot"}, "$unset": {"booking_flow.slot_id": ""}},
        )
        await _store_inbound(
            tenant_id, conversation_id, text, message_id, action_id=action_id
        )
        repick_key = f"booking-repick:{conversation_id}:{message_id}"
        repick = await send_slot_picker(
            tenant_id,
            wa_id,
            prompt=t("booking.repick_prompt", lang),
            slots=picker_slots,
            operation_key=repick_key,
            button_label=t("ui.choose_time", lang),
            section_title=t("ui.slots_title", lang),
        )
        await _record_flow_interactive(
            tenant_id,
            conversation_id,
            repick_key,
            "booking_slot_picker",
            repick,
        )
        return True

    if action_id == "booking:confirm" and flow.get("stage") == "awaiting_confirmation":
        slot_id = str(flow.get("slot_id", ""))
        request_id = f"booking-flow:{conversation_id}:{slot_id}:{flow.get('kind', 'create')}"
        if flow.get("kind") == "move":
            result = await booking_move(
                tenant_id,
                str(flow.get("booking_id", "")),
                slot_id,
                request_id,
                date_confirmed=True,
                contact_id=contact_id,
            )
        else:
            result = await booking_create(
                tenant_id,
                slot_id,
                contact_id,
                str(flow.get("service", "Consultation")),
                request_id,
                date_confirmed=True,
            )
        await _store_inbound(
            tenant_id, conversation_id, text, message_id, action_id=action_id
        )
        if result.get("status") == "success":
            slot_val = flow.get("slots", {}).get(slot_id, "")
            when_str = _render_slot_label(slot_val, tenant_tz, lang)
            response_key = "booking.rescheduled" if flow.get("kind") == "move" else "booking.booked"
            response = t(response_key, lang, when=when_str)
            result_key = f"booking-result:{request_id}"
            await _send_flow_text(
                tenant_id,
                wa_id,
                conversation_id,
                response,
                result_key,
            )
            await Conversations(tenant_id).update_one(
                {"_id": conversation_db_id, "state": "bot"},
                {
                    "$set": {
                        "booking_flow.stage": "completed",
                        "booking_flow.result": result,
                        "booking_flow.result_text": response,
                        "booking_flow.result_operation_key": result_key,
                    }
                },
            )
        else:
            remaining_slots = {
                key: value
                for key, value in flow.get("slots", {}).items()
                if key != slot_id
            }
            if remaining_slots:
                recovery_key = f"booking-recovery:{request_id}"
                recovery_picker_slots = [
                    {"slot_id": key, "label": _render_slot_label(value, tenant_tz, lang)}
                    for key, value in remaining_slots.items()
                ]
                recovery = await send_slot_picker(
                    tenant_id,
                    wa_id,
                    prompt=t("booking.slot_taken_repick", lang),
                    slots=recovery_picker_slots,
                    operation_key=recovery_key,
                    button_label=t("ui.choose_time", lang),
                    section_title=t("ui.slots_title", lang),
                )
                await _record_flow_interactive(
                    tenant_id,
                    conversation_id,
                    recovery_key,
                    "booking_slot_picker",
                    recovery,
                )
                next_stage = "choose_slot"
            else:
                await _send_flow_text(
                    tenant_id,
                    wa_id,
                    conversation_id,
                    t("booking.slot_taken_none", lang),
                    f"booking-recovery:{request_id}",
                )
                next_stage = "needs_new_search"
            recovered_flow = {
                **flow,
                "stage": next_stage,
                "slots": remaining_slots,
                "result": result,
            }
            recovered_flow.pop("slot_id", None)
            await Conversations(tenant_id).update_one(
                {"_id": conversation_db_id, "state": "bot"},
                {"$set": {"booking_flow": recovered_flow}},
            )
        return True
    if action_id == "booking:confirm" and flow.get("stage") == "completed":
        result = flow.get("result", {})
        if isinstance(result, dict) and result.get("status") == "success":
            slot_id = str(flow.get("slot_id", ""))
            slot_val = flow.get("slots", {}).get(slot_id, "the selected time")
            when_str = _render_slot_label(slot_val, tenant_tz, lang)
            await _store_inbound(
                tenant_id, conversation_id, text, message_id, action_id=action_id
            )
            await _send_flow_text(
                tenant_id,
                wa_id,
                conversation_id,
                t("booking.already_confirmed", lang, when=when_str),
                f"booking-repeat:{message_id or conversation_id}:{slot_id}",
            )
            return True
    return False


async def process_event(fields: dict[str, Any]) -> None:
    """Run one inbound event end-to-end: agent graph -> WhatsApp reply."""
    from app.observability import bind, clear

    tenant_id = fields["tenant_id"]
    message_id = fields.get("message_id")
    bind(tenant_id=tenant_id, message_id=message_id)
    try:
        await _process_event_inner(fields, tenant_id, message_id)
    finally:
        clear()


async def _process_event_inner(
    fields: dict[str, Any], tenant_id: str, message_id: str | None
) -> None:
    from app.observability import bind

    payload = json.loads(fields["payload"])

    parsed = _parse_message(payload)
    if not parsed:
        return

    if not parsed["text"]:
        msg_type = parsed.get("message_type", "")
        if msg_type in UNSUPPORTED_TYPES:
            wa_id = parsed["wa_id"]
            conversation_id, conversation_state, conversation_db_id, contact_id = (
                await _resolve_conversation(tenant_id, wa_id, parsed["profile_name"])
            )
            bind(conversation_id=conversation_id)
            await _store_inbound(
                tenant_id,
                conversation_id,
                "",
                message_id,
                message_type=msg_type,
            )
            if conversation_state == "human":
                return
            lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)
            await _send_flow_text(
                tenant_id,
                wa_id,
                conversation_id,
                t("media.unsupported", lang),
                f"unsupported:{message_id or conversation_id}",
            )
            return
        logger.info("Skipping non-text / unsupported inbound event of type: %s", msg_type)
        return

    wa_id, text = parsed["wa_id"], parsed["text"]
    conversation_id, conversation_state, conversation_db_id, contact_id = (
        await _resolve_conversation(tenant_id, wa_id, parsed["profile_name"])
    )
    bind(conversation_id=conversation_id)

    try:
        from app.billing.meters import record_usage

        await record_usage(
            tenant_id,
            event_id=f"wa_conv:{conversation_id}",
            metric="wa_conversations",
            quantity=1,
            occurred_at=datetime.now(UTC),
        )
    except Exception as usage_err:
        logger.warning("Failed to meter wa_conversations usage: %s", usage_err)

    await audit.record(
        tenant_id,
        actor="user",
        event_type="inbound_message",
        payload={"wa_id": wa_id, "text": text},
        conversation_id=conversation_id,
        operation_key=f"inbound:{message_id}" if message_id else None,
    )

    messages = Messages(tenant_id)
    if conversation_state == "human":
        document = {
            "conversation_id": conversation_id,
            "direction": "inbound",
            "type": "text",
            "text": text,
            "ts": _now(),
        }
        if message_id:
            await Messages.upsert_message_unscoped(message_id, tenant_id, document)
        else:
            await messages.insert_one(document)
        return

    upper_text = text.strip().upper()
    if upper_text in {"STOP", "UNSUBSCRIBE"}:
        await Contacts(tenant_id).update_one(
            {"_id": {"$in": mongo_id_candidates(contact_id)}},
            {"$set": {"messaging_opt_out": True, "opt_out_at": _now()}},
        )
        await _store_inbound(
            tenant_id,
            conversation_id,
            text,
            message_id,
            intent="opt_out",
        )
        reply_key = f"optout:{message_id or conversation_id}"
        lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)
        await send_freeform(
            tenant_id,
            wa_id,
            t("optout.done", lang),
            operation_key=reply_key,
        )
        return

    if upper_text in {"START", "SUBSCRIBE", "UNSTOP"}:
        await Contacts(tenant_id).update_one(
            {"_id": {"$in": mongo_id_candidates(contact_id)}},
            {"$set": {"messaging_opt_out": False}, "$unset": {"opt_out_at": ""}},
        )
        await _store_inbound(
            tenant_id,
            conversation_id,
            text,
            message_id,
            intent="opt_in",
        )
        reply_key = f"optin:{message_id or conversation_id}"
        lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)
        await send_freeform(
            tenant_id,
            wa_id,
            t("optin.done", lang),
            operation_key=reply_key,
        )
        return

    if await _handle_cancel_action(
        tenant_id=tenant_id,
        wa_id=wa_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        conversation_db_id=conversation_db_id,
        message_id=str(message_id) if message_id else None,
        text=text,
        action_id=str(parsed.get("action_id", "")),
    ):
        return

    if await _handle_booking_action(
        tenant_id=tenant_id,
        wa_id=wa_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        conversation_db_id=conversation_db_id,
        message_id=str(message_id) if message_id else None,
        text=text,
        action_id=str(parsed.get("action_id", "")),
    ):
        return

    app = build_graph()
    state = {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "channel": "wa",
        "text": text,
    }
    result = await app.ainvoke(state)
    response = strip_citations(result.get("response", ""))

    detected = normalize_lang(result.get("lang"))
    has_non_latin = bool(re.search(r"[^\x00-\x7F]", text))
    has_min_words = len(text.split()) >= 3
    if has_non_latin or has_min_words:
        lang = detected
        await Conversations(tenant_id).update_one(
            {"_id": conversation_db_id},
            {"$set": {"lang": lang}},
        )
        await Contacts(tenant_id).update_one(
            {"_id": {"$in": mongo_id_candidates(contact_id)}},
            {"$set": {"lang_pref": lang}},
        )
    else:
        lang = await _conversation_lang(tenant_id, conversation_db_id, contact_id)

    intent = result.get("intent")
    if intent == "booking_status":
        booking = await Bookings(tenant_id).find_one(
            {
                "contact_id": {"$in": mongo_id_candidates(contact_id)},
                "status": {"$in": ["confirmed", "rescheduled"]},
            }
        )
        if booking:
            slot = await Slots(tenant_id).find_one(
                {"_id": {"$in": mongo_id_candidates(str(booking["slot_id"]))}}
            )
            start = slot.get("start") if slot else None
            tenant = await Tenants.find_by_id(tenant_id)
            tenant_tz = tenant_timezone(tenant)
            if isinstance(start, datetime):
                when = format_local(start, tenant_tz, lang=lang)
            else:
                when = "unknown time"
            status_val = str(booking.get("status", "confirmed"))
            try:
                status_word = t(f"status.word.{status_val}", lang)
            except KeyError:
                status_word = status_val
            response = t("status.found", lang, status=status_word, when=when)
        else:
            response = t("status.none", lang)
    elif intent == "cancel":
        booking = await Bookings(tenant_id).find_one(
            {
                "contact_id": {"$in": mongo_id_candidates(contact_id)},
                "status": {"$in": ["confirmed", "rescheduled"]},
            }
        )
        if booking:
            slot = await Slots(tenant_id).find_one(
                {"_id": {"$in": mongo_id_candidates(str(booking["slot_id"]))}}
            )
            tenant = await Tenants.find_by_id(tenant_id)
            tenant_tz = tenant_timezone(tenant)
            start = slot.get("start") if slot else None
            if isinstance(start, datetime):
                when = format_local(start, tenant_tz, lang=lang)
            else:
                when = "your appointment"

            await Conversations(tenant_id).update_one(
                {"_id": conversation_db_id, "state": "bot"},
                {
                    "$set": {
                        "cancel_flow": {
                            "stage": "awaiting_confirmation",
                            "booking_id": str(booking["_id"]),
                            "when": when,
                            "created_at": _now(),
                        }
                    }
                },
            )
            await _store_inbound(
                tenant_id,
                conversation_id,
                text,
                message_id,
                intent="cancel",
                confidence=result.get("confidence"),
            )
            prompt = t("cancel.prompt", lang, when=when)
            operation_key = f"cancel-confirm:{message_id or conversation_id}"
            send_res = await send_cancel_confirmation(
                tenant_id,
                wa_id,
                prompt=prompt,
                operation_key=operation_key,
                yes_title=t("ui.cancel_yes", lang),
                keep_title=t("ui.cancel_keep", lang),
            )
            await _record_flow_interactive(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                operation_key=operation_key,
                flow="cancel_confirmation",
                result=send_res,
            )
            return
        else:
            response = t("status.none", lang)
    elif intent in {"book", "reschedule"}:
        existing_booking = None
        if intent == "reschedule":
            existing_booking = await Bookings(tenant_id).find_one(
                {
                    "contact_id": {"$in": mongo_id_candidates(contact_id)},
                    "status": {"$in": ["confirmed", "rescheduled"]},
                }
            )
            if not existing_booking:
                response = t("reschedule.none", lang)

        slots_tool_res = next(
            (
                item
                for item in result.get("tool_results", [])
                if item.get("tool") == "slots_get"
            ),
            None,
        )
        has_slots = bool(slots_tool_res and slots_tool_res.get("result"))

        if slots_tool_res and has_slots and (intent == "book" or existing_booking):
            tenant = await Tenants.find_by_id(tenant_id)
            tenant_tz = tenant_timezone(tenant)
            picker_slots = []
            stored_slots: dict[str, str] = {}
            for slot in slots_tool_res["result"][:10]:
                slot_id = str(slot["slot_id"])
                start_raw = str(slot["start"])
                stored_slots[slot_id] = start_raw
                label = _render_slot_label(start_raw, tenant_tz, lang)
                picker_slots.append({"slot_id": slot_id, "label": label})
            flow = {
                "stage": "choose_slot",
                "kind": "move" if intent == "reschedule" else "create",
                "booking_id": str(existing_booking["_id"]) if existing_booking else None,
                "practitioner_id": slots_tool_res["practitioner_id"],
                "practitioner_name": slots_tool_res["practitioner_name"],
                "service": "Consultation",
                "date": slots_tool_res["date"],
                "slots": stored_slots,
            }
            await Conversations(tenant_id).update_one(
                {"_id": conversation_db_id, "state": "bot"},
                {"$set": {"booking_flow": flow}},
            )
            await _store_inbound(
                tenant_id,
                conversation_id,
                text,
                str(message_id) if message_id else None,
                intent=str(intent),
                confidence=result.get("confidence"),
            )
            picker_key = f"booking-picker:{message_id or conversation_id}"
            picker_prompt = t(
                "booking.picker_prompt",
                lang,
                service=flow["service"],
                practitioner=flow["practitioner_name"],
                date=flow["date"],
            )
            picker = await send_slot_picker(
                tenant_id,
                wa_id,
                prompt=picker_prompt,
                slots=picker_slots,
                operation_key=picker_key,
                button_label=t("ui.choose_time", lang),
                section_title=t("ui.slots_title", lang),
            )
            await _record_flow_interactive(
                tenant_id,
                conversation_id,
                picker_key,
                "booking_slot_picker",
                picker,
            )
            return
        elif not has_slots and (intent == "book" or existing_booking):
            raw_date = slots_tool_res.get("date") if slots_tool_res else ""
            human_date = raw_date
            if raw_date:
                try:
                    d_parsed = date.fromisoformat(raw_date)
                    human_date = d_parsed.strftime("%d %b %Y")
                except Exception:
                    pass
            response = t("booking.no_slots", lang, date=human_date or "that date")

    document = {
        "conversation_id": conversation_id,
        "direction": "inbound",
        "type": "text",
        "text": text,
        "intent": result.get("intent"),
        "confidence": result.get("confidence"),
        "ts": _now(),
    }
    if message_id:
        await Messages.upsert_message_unscoped(
            message_id=message_id,
            tenant_id=tenant_id,
            document=document,
        )
    else:
        await messages.insert_one(document)

    if not response:
        logger.warning("Agent produced an empty response for %s; nothing to send", conversation_id)
        return

    # Takeover may occur while the agent is working; ownership wins over a queued reply.
    conversation = await Conversations(tenant_id).find_one({"_id": conversation_db_id})
    handoff_ack = bool(
        conversation
        and conversation.get("state") == "human"
        and result.get("escalate")
    )
    if not conversation or (conversation.get("state") != "bot" and not handoff_ack):
        logger.info("Suppressing bot reply after conversation ownership changed")
        return

    try:
        await send_freeform(
            tenant_id,
            wa_id,
            response,
            operation_key=f"reply:{message_id or conversation_id}",
        )
    except WindowClosedError:
        # Directly after an inbound message the window is open, so this is an edge
        # case (clock skew / very slow processing). Escalate rather than drop.
        logger.warning("24h window closed while replying to %s; leaving for staff", conversation_id)
        await audit.record(
            tenant_id,
            actor="system",
            event_type="reply_window_closed",
            payload={"wa_id": wa_id, "response": response},
            conversation_id=conversation_id,
        )
        return

    operation_key = f"reply:{message_id or conversation_id}"
    await messages.update_one(
        {"operation_key": operation_key},
        {
            "$setOnInsert": {
                "conversation_id": conversation_id,
                "direction": "outbound",
                "type": "text",
                "text": response,
                "operation_key": operation_key,
                "ts": _now(),
            }
        },
        upsert=True,
    )


async def _ensure_group(r: Any) -> None:
    try:
        await r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as e:  # redis.ResponseError: BUSYGROUP already exists
        if "BUSYGROUP" not in str(e):
            raise


async def _dead_letter(r: Any, msg_id: str, fields: dict[str, Any], reason: str) -> None:
    logger.error("Dead-lettering %s after %d attempts: %s", msg_id, MAX_DELIVERIES, reason)
    durable_id = str(fields.get("message_id", msg_id))
    await Messages.mark_failed_unscoped(durable_id, reason=reason)
    await r.xadd(DEAD_LETTER, {**fields, "failed_msg_id": msg_id, "reason": reason})
    await r.xack(STREAM, GROUP, msg_id)
    tenant_id = str(fields.get("tenant_id", "system"))
    await audit.record(
        tenant_id,
        actor="system",
        event_type="operational_alert",
        payload={"kind": "dead_letter", "failed_msg_id": msg_id, "reason": reason},
        operation_key=f"dlq-alert:{msg_id}",
    )


async def check_queue_age(
    r: Any, *, max_age_seconds: float = 60.0, now_ts: float | None = None
) -> float | None:
    """Inspect oldest pending stream entry and alert if older than threshold."""
    try:
        pending = await r.xpending(STREAM, GROUP)
        if not pending or not pending.get("pending") or not pending.get("min"):
            return None
        min_id = str(pending["min"])
        min_ms = float(min_id.split("-")[0])
        current_s = now_ts if now_ts is not None else datetime.now(UTC).timestamp()
        age_seconds = current_s - (min_ms / 1000.0)
        if age_seconds > max_age_seconds:
            await audit.record(
                "system",
                actor="system",
                event_type="operational_alert",
                payload={
                    "kind": "queue_age",
                    "age_seconds": round(age_seconds, 2),
                    "threshold_seconds": max_age_seconds,
                    "pending_count": pending.get("pending", 0),
                },
                operation_key=f"queue-age-alert:{int(current_s // 60)}",
            )
        return age_seconds
    except Exception as exc:
        logger.debug("check_queue_age check skipped: %s", exc)
        return None


async def _handle(r: Any, msg_id: str, fields: dict[str, Any], deliveries: int) -> None:
    durable_id = fields.get("message_id", msg_id)
    if not await Messages.acquire_work_unscoped(durable_id):
        await r.xack(STREAM, GROUP, msg_id)
        return
    try:
        await process_event(fields)
        await Messages.mark_completed_unscoped(durable_id)
        await r.xack(STREAM, GROUP, msg_id)
    except Exception as e:
        await Messages.release_work_unscoped(durable_id, str(e))
        if deliveries >= MAX_DELIVERIES:
            await _dead_letter(r, msg_id, fields, type(e).__name__)
        else:
            # Leave un-ACKed: it stays pending and is reclaimed for another attempt.
            logger.warning("Processing %s failed (attempt %d): %s", msg_id, deliveries, e)


async def _process_fallback_queue() -> None:
    """Scan MongoDB for status='queued' messages and process them."""
    try:
        queued_messages = await Messages.find_queued_unscoped()
        for doc in queued_messages:
            message_id = doc["_id"]
            tenant_id = doc["tenant_id"]
            retries = doc.get("attempts", 0)

            if retries >= MAX_DELIVERIES:
                logger.error(
                    "Fallback message %s exceeded max retries, marking as failed", message_id
                )
                await Messages.mark_failed_unscoped(message_id, reason="Max retries reached")
                continue

            logger.info(
                "Processing fallback queue message %s (attempt %d) for tenant %s",
                message_id, retries + 1, tenant_id,
            )
            fields = {
                "tenant_id": tenant_id,
                "message_id": message_id,
                "payload": json.dumps(doc["payload"])
            }
            if not await Messages.acquire_work_unscoped(str(message_id)):
                continue
            try:
                await process_event(fields)
                await Messages.mark_completed_unscoped(str(message_id))
            except Exception as e:
                logger.warning("Processing fallback message %s failed: %s", message_id, e)
                await Messages.release_work_unscoped(str(message_id), str(e))
    except Exception as e:
        logger.error("Failed to process fallback queue: %s", e, exc_info=True)


async def run_scheduler_background() -> None:
    """Background task to run reminders, daily briefs and weekly summaries on schedule."""
    logger.info("Starting background scheduler...")
    from app.booking.engine import run_schedule_expansion
    from app.models.collections import OutboundIntents
    from app.workers.billing import run_monthly_invoices
    from app.workers.daily_brief import run_daily_briefs
    from app.workers.escalations import run_escalation_slas
    from app.workers.reminders import run_reminders
    from app.workers.weekly_summary import run_weekly_summaries

    while True:
        try:
            reconciled = await OutboundIntents.mark_stale_sending_unknown_unscoped()
            if reconciled:
                logger.warning("Marked %d interrupted outbound sends unknown", reconciled)
                await audit.record(
                    "system",
                    actor="system",
                    event_type="operational_alert",
                    payload={"kind": "unknown_delivery", "reconciled_count": reconciled},
                )
        except Exception as e:
            logger.error("Background scheduler error in send reconciliation: %s", e)

        # Run reminders every 15 minutes
        try:
            await run_schedule_expansion()
        except Exception as e:
            logger.error("Background scheduler error in slot expansion: %s", e, exc_info=True)

        try:
            logger.info("Background scheduler: running reminders scan...")
            await run_reminders()
        except Exception as e:
            logger.error("Background scheduler error in reminders: %s", e, exc_info=True)

        try:
            await run_escalation_slas()
        except Exception as e:
            logger.error("Background scheduler error in escalation SLAs: %s", e, exc_info=True)

        try:
            await run_monthly_invoices()
        except Exception as e:
            logger.error("Background scheduler error in billing: %s", e, exc_info=True)

        try:
            await run_daily_briefs()
        except Exception as e:
            logger.error("Background scheduler error in daily briefs: %s", e, exc_info=True)

        try:
            await run_weekly_summaries()
        except Exception as e:
            logger.error("Background scheduler error in weekly summaries: %s", e, exc_info=True)

        await asyncio.sleep(15 * 60)  # Check every 15 minutes


async def run(iterations: int | None = None) -> None:
    """Consume the inbound stream. `iterations=None` runs forever (worker mode)."""
    settings.validate_runtime()
    r: Any = get_redis()  # redis-py stream ops are dynamically typed
    group_ready = False

    scheduler_task = asyncio.create_task(run_scheduler_background())

    try:
        count = 0
        while iterations is None or count < iterations:
            count += 1

            # Process any fallback queue messages from MongoDB
            await _process_fallback_queue()

            try:
                if not group_ready:
                    await _ensure_group(r)
                    group_ready = True
                    logger.info("Inbound worker consuming %s as %s/%s", STREAM, GROUP, CONSUMER)
                await r.set("vaani:worker:heartbeat", str(_now().timestamp()), ex=60)
            except Exception as e:
                logger.warning("Redis unavailable; continuing MongoDB recovery scan: %s", e)
                await asyncio.sleep(1)
                continue

            # Reclaim stalled/failed pending messages, dead-lettering the exhausted ones.
            try:
                _, claimed, _ = await r.xautoclaim(
                    STREAM, GROUP, CONSUMER, min_idle_time=_IDLE_RECLAIM_MS, start_id="0"
                )
                for msg_id, fields in claimed:
                    pending = await r.xpending_range(STREAM, GROUP, msg_id, msg_id, 1)
                    deliveries = int(pending[0]["times_delivered"]) if pending else MAX_DELIVERIES
                    await _handle(r, msg_id, fields, deliveries)
            except Exception as e:
                logger.debug("xautoclaim skipped: %s", e)

            try:
                resp = await r.xreadgroup(
                    GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000
                )
            except Exception as e:
                # Transient network/timeout on the blocking read must not kill the
                # consumer loop — log and retry rather than crash-looping the process.
                logger.warning("xreadgroup failed, retrying: %s", e)
                continue

            if not resp:
                continue
            for _stream, entries in resp:
                for msg_id, fields in entries:
                    await _handle(r, msg_id, fields, deliveries=1)
    finally:
        scheduler_task.cancel()


def main() -> None:
    from app.observability import init_observability

    init_observability("worker")
    logger.info("Starting inbound worker...")
    asyncio.run(run())


if __name__ == "__main__":
    main()
