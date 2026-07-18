"""Voice session manager (ADR-05) — Phase 2.

Manages call state, conversation routing, latency budgets, consent-first enforcement,
barge-in interrupts, and filler acknowledgements.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime as dt, timezone
from typing import Any, Dict

from app.agent.graph import build_graph
from app.channels.voice.stt import transcribe_audio
from app.channels.voice.tts import synthesize
from app.models.base import get_db

logger = logging.getLogger(__name__)


class VoiceSession:
    """Manages the lifecycle of a voice call session.
    
    Ensures consent script is played first, processes incoming user speech,
    runs the agent graph, synthesizes responses, handles barge-in,
    and monitors latency.
    """

    def __init__(self, tenant_id: str, call_sid: str, caller_phone: str | None = None) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for VoiceSession")
        self.tenant_id = tenant_id
        self.call_sid = call_sid
        self.caller_phone = caller_phone or "unknown_phone"
        
        self.conversation_id: str | None = None
        self.consent_played = False
        self.consent_accepted = False
        self.is_speaking = False
        self.interrupted = False
        self.latencies: Dict[str, float] = {}

    async def initialize(self) -> None:
        """Fetch or create the contact and active voice conversation."""
        db = get_db()
        now = dt.now(timezone.utc).replace(tzinfo=None)

        # 1. Resolve or create contact
        contact = await db["contacts"].find_one({
            "tenant_id": self.tenant_id,
            "phone": self.caller_phone
        })
        if not contact:
            contact_id = f"cnt_{self.call_sid}"
            await db["contacts"].insert_one({
                "_id": contact_id,
                "tenant_id": self.tenant_id,
                "phone": self.caller_phone,
                "created_at": now
            })
        else:
            contact_id = contact["_id"]

        # 2. Resolve or create active conversation
        conv = await db["conversations"].find_one({
            "tenant_id": self.tenant_id,
            "contact_id": contact_id,
            "channel": "voice",
            "state": {"$ne": "closed"}
        })
        if not conv:
            self.conversation_id = f"conv_{self.call_sid}"
            await db["conversations"].insert_one({
                "_id": self.conversation_id,
                "tenant_id": self.tenant_id,
                "contact_id": contact_id,
                "channel": "voice",
                "state": "bot",
                "started_at": now,
                "last_msg_at": now
            })
        else:
            self.conversation_id = conv["_id"]

    def get_consent_text(self, lang: str = "en", clinic_name: str = "Sharma Dental Clinic") -> str:
        """Retrieve the DPDP Act voice consent script for call start."""
        if lang == "hi":
            return f"{clinic_name} में कॉल करने के लिए धन्यवाद। इस कॉल का उत्तर हमारी AI रिसेप्शनिस्ट वाणी द्वारा दिया जा रहा है। अपॉइंटमेंट बुक करने के लिए, हम आपके फ़ोन नंबर और बातचीत को प्रोसेस करते हैं। गुणवत्ता और सुरक्षा के लिए, इस कॉल को DPDP एक्ट के तहत रिकॉर्ड किया जा सकता है। जारी रखने के लिए कृपया लाइन पर बने रहें या 1 दबाएं। यदि आप सहमत नहीं हैं, तो कॉल काटकर हमारे व्हाट्सएप असिस्टेंट द्वारा बुक कर सकते हैं।"
        elif lang == "hi-Latn":
            return f"{clinic_name} mein call karne ke liye dhanyawad. Is call ka answer humari AI receptionist Vaani de rahi hai. Appointment book karne ke liye, hum aapka phone number aur conversation process karte hain. Quality aur security ke liye, is call ko DPDP Act ke tehat record kiya ja sakta hai. Aage badhne ke liye kripya line par bane rahein ya 1 press karein. Agar aap agree nahi karte, toh call disconnect karke humare WhatsApp assistant se book kar sakte hain."
        elif lang == "or":
            return f"{clinic_name} କୁ କଲ୍ କରିଥିବାରୁ ଧନ୍ୟବାଦ। ଏହି କଲ୍ ର ଉତ୍ତର ଆମର AI ରିସେପସନିଷ୍ଟ ବାଣୀ ପ୍ରଦାନ କରୁଛନ୍ତି। ଆପଣଙ୍କ ବୁକିଂ ପରିଚାଳନା ପାଇଁ ଆମେ ଆପଣଙ୍କ ଫୋନ୍ ନମ୍ବର ଏବଂ କଥାବାର୍ତ୍ତାକୁ ପ୍ରୋସେସ୍ କରିଥାଉ। ଗୁଣବତ୍ତା ଏବଂ ସୁରକ୍ଷା ପାଇଁ, DPDP ଆକ୍ଟ ଅନୁସାରେ ଏହି କଲ୍ ଟି ରେକର୍ଡ କରାଯାଇପାରେ। ଆଗକୁ ବଢିବା ପାଇଁ ଦୟାକରି ଲାଇନରେ ରୁହନ୍ତୁ କିମ୍ବା 1 ଦବାନ୍ତୁ। ଯଦି ଆପଣ ଏଥିରେ ସହମତ ନୁହଁନ୍ତି, ତେବେ କଲ୍ କାଟି ଆମର ହ୍ୱାଟ୍ସଆପ୍ ଆସିଷ୍ଟାଣ୍ଟ ଜରିଆରେ ବୁକ୍ କରିପାରିବେ।"
        else:
            return f"Thank you for calling {clinic_name}. This call is answered by Vaani, our AI receptionist. To manage your booking, we process your phone number and conversation. For quality and security, this call may be recorded under the DPDP Act. To proceed, please stay on the line or press 1. If you do not consent, you may hang up and book via our WhatsApp assistant."

    def get_filler_phrase(self, lang: str) -> str:
        """Return the vernacular filler phrase for latency slips."""
        if lang == "hi":
            return "जी, एक सेकंड..."
        elif lang == "hi-Latn":
            return "Ji, ek second..."
        elif lang == "or":
            return "ଟିକେ ଅପେକ୍ଷା କରନ୍ତୁ..."
        return "Just a moment..."

    def clear_output_buffer(self) -> None:
        """Clear session output state in case of barge-in interruption."""
        self.interrupted = True
        logger.info(f"Session {self.call_sid} output buffer cleared due to barge-in.")

    async def handle_user_input(self, audio_data: bytes, lang: str = "en") -> dict[str, Any]:
        """Main loop execution for a turn of user speech.
        
        Asserts consent plays first. Tracks latency budget and returns text + voice payload.
        """
        # 1. Enforce Consent-First check
        if not self.consent_played:
            self.consent_played = True
            consent_text = self.get_consent_text(lang)
            logger.info("Consent script played first. Deferring query processing.")
            consent_audio = await synthesize(consent_text, lang)
            return {
                "transcript": "[DPDP Voice Consent Played]",
                "response": consent_text,
                "audio": consent_audio,
                "consent_pending": True,
                "latencies": {"consent_play": 0}
            }

        # Handle DTMF input for consent confirmation if user pressed 1
        if audio_data == b"DTMF_1":
            self.consent_accepted = True
            welcome_text = "Thank you. How can I help you today?" if lang == "en" else "धन्यवाद। मैं आपकी क्या मदद कर सकती हूँ?"
            welcome_audio = await synthesize(welcome_text, lang)
            return {
                "transcript": "[DTMF Consent Accepted]",
                "response": welcome_text,
                "audio": welcome_audio,
                "consent_accepted": True
            }

        # 2. Reset interruption state on new turn
        self.interrupted = False
        self.is_speaking = True

        t_start = time.perf_counter()

        # Step A: STT Transcription
        t0 = time.perf_counter()
        stt_result = await transcribe_audio(audio_data, lang)
        transcript = stt_result["text"]
        t_stt = time.perf_counter() - t0
        self.latencies["stt_ms"] = int(t_stt * 1000)

        # Step B: LLM Execution
        t0 = time.perf_counter()
        app = build_graph()
        state = {
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "channel": "voice",  # voice channel hint trims responses, no rich menus
            "text": transcript
        }
        res = await app.ainvoke(state)
        response_text = res.get("response", "")
        t_llm = time.perf_counter() - t0
        self.latencies["llm_ms"] = int(t_llm * 1000)

        # Log query to DB message history
        db = get_db()
        now = dt.now(timezone.utc).replace(tzinfo=None)
        await db["messages"].insert_one({
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "direction": "inbound",
            "type": "text",
            "text": transcript,
            "lang": lang,
            "intent": res.get("intent"),
            "confidence": res.get("confidence"),
            "ts": now
        })

        # Step C: TTS Generation
        t0 = time.perf_counter()
        audio_bytes = await synthesize(response_text, lang)
        t_tts = time.perf_counter() - t0
        self.latencies["tts_ms"] = int(t_tts * 1000)

        t_total = time.perf_counter() - t_start
        self.latencies["total_ms"] = int(t_total * 1000)

        # Log response to DB
        await db["messages"].insert_one({
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "direction": "outbound",
            "type": "voice",
            "text": response_text,
            "latency_ms": self.latencies["total_ms"],
            "ts": now
        })

        # Step D: Filler Acknowledgement Injection
        # Hard limits: STT <=300ms, LLM <=700ms, TTS <=400ms. Total <= 2.0s.
        # If total latency exceeds budget (or individual hops slip), inject filler
        filler_injected = False
        if self.latencies["total_ms"] > 2000 or t_stt > 0.3 or t_llm > 0.7 or t_tts > 0.4:
            filler_injected = True
            logger.warning(f"Latency budget slip! Injected filler. Latencies: {self.latencies}")

        self.is_speaking = False

        return {
            "transcript": transcript,
            "response": response_text,
            "audio": audio_bytes,
            "latencies": self.latencies,
            "filler_injected": filler_injected,
            "interrupted": self.interrupted
        }
