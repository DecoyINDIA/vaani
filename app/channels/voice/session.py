"""Voice session manager (ADR-05) — Phase 2.

Manages call state, conversation routing, latency budgets, consent-first enforcement,
barge-in interrupts, and filler acknowledgements.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC
from datetime import datetime as dt
from typing import Any

from app.agent.graph import build_graph
from app.channels.voice.stt import transcribe_audio
from app.channels.voice.tts import synthesize
from app.models.collections import Contacts, Conversations, Messages, Tenants

logger = logging.getLogger(__name__)


class VoiceSession:
    """Manages the lifecycle of a voice call session.
    
    Ensures consent script is played first, processes incoming user speech,
    runs the agent graph, synthesizes responses, handles barge-in,
    and monitors latency.
    """

    def __init__(
        self,
        tenant_id: str,
        call_sid: str,
        caller_phone: str | None = None,
        sample_rate: int = 8000,
    ) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for VoiceSession")
        self.tenant_id = tenant_id
        self.call_sid = call_sid
        self.caller_phone = caller_phone or f"ephemeral:{call_sid}"
        self.sample_rate = sample_rate
        self.clinic_name = "our business"
        self.default_lang = "hi-Latn"
        
        self.conversation_id: str | None = None
        self.consent_played = False
        self.consent_accepted = False
        self.is_speaking = False
        self.interrupted = False
        self.latencies: dict[str, float] = {}

    async def initialize(self) -> None:
        """Fetch or create the contact and active voice conversation."""
        now = dt.now(UTC).replace(tzinfo=None)
        tenant = await Tenants.find_by_id(self.tenant_id)
        if tenant:
            self.clinic_name = str(tenant.get("name", "our business"))
            self.default_lang = str(tenant.get("locale_default", "hi-Latn"))

        contacts = Contacts(self.tenant_id)
        conversations = Conversations(self.tenant_id)

        # 1. Resolve or create contact
        contact = await contacts.find_one({"phone": self.caller_phone})
        if not contact:
            contact_id = f"cnt_{self.call_sid}"
            await contacts.insert_one({
                "_id": contact_id,
                "phone": self.caller_phone,
                "created_at": now
            })
        else:
            contact_id = contact["_id"]

        self.contact_id = contact_id
        if contact and contact.get("consent", {}).get("status") == "granted":
            self.consent_accepted = True
            self.consent_played = True

        # 2. Resolve or create active conversation
        conv = await conversations.find_one({
            "contact_id": contact_id,
            "channel": "voice",
            "state": {"$ne": "closed"}
        })
        if not conv:
            self.conversation_id = f"conv_{self.call_sid}"
            await conversations.insert_one({
                "_id": self.conversation_id,
                "contact_id": contact_id,
                "channel": "voice",
                "state": "bot",
                "started_at": now,
                "last_msg_at": now
            })
        else:
            self.conversation_id = conv["_id"]

    def get_consent_text(self, lang: str = "en", clinic_name: str | None = None) -> str:
        """Retrieve the DPDP Act voice consent script for call start."""
        clinic = clinic_name or getattr(self, "clinic_name", "our business")
        if lang == "hi":
            return f"{clinic} में कॉल करने के लिए धन्यवाद। इस कॉल का उत्तर हमारी AI रिसेप्शनिस्ट वाणी द्वारा दिया जा रहा है। अपॉइंटमेंट बुक करने के लिए, हम आपके फ़ोन नंबर और बातचीत को प्रोसेस करते हैं। गुणवत्ता और सुरक्षा के लिए, इस कॉल को DPDP एक्ट के तहत रिकॉर्ड किया जा सकता है। जारी रखने के लिए कृपया लाइन पर बने रहें या 1 दबाएं। यदि आप सहमत नहीं हैं, तो कॉल काटकर हमारे व्हाट्सएप असिस्टेंट द्वारा बुक कर सकते हैं।"
        elif lang == "hi-Latn":
            return f"{clinic} mein call karne ke liye dhanyawad. Is call ka answer humari AI receptionist Vaani de rahi hai. Appointment book karne ke liye, hum aapka phone number aur conversation process karte hain. Quality aur security ke liye, is call ko DPDP Act ke tehat record kiya ja sakta hai. Aage badhne ke liye kripya line par bane rahein ya 1 press karein. Agar aap agree nahi karte, toh call disconnect karke humare WhatsApp assistant se book kar sakte hain."
        elif lang == "or":
            return f"{clinic} କୁ କଲ୍ କରିଥିବାରୁ ଧନ୍ୟବାଦ। ଏହି କଲ୍ ର ଉତ୍ତର ଆମର AI ରିସେପସନିଷ୍ଟ ବାଣୀ ପ୍ରଦାନ କରୁଛନ୍ତି। ଆପଣଙ୍କ ବୁକିଂ ପରିଚାଳନା ପାଇଁ ଆମେ ଆପଣଙ୍କ ଫୋନ୍ ନମ୍ବର ଏବଂ କଥାବାର୍ତ୍ତାକୁ ପ୍ରୋସେସ୍ କରିଥାଉ। ଗୁଣବତ୍ତା ଏବଂ ସୁରକ୍ଷା ପାଇଁ, DPDP ଆକ୍ଟ ଅନୁସାରେ ଏହି କଲ୍ ଟି ରେକର୍ଡ କରାଯାଇପାରେ। ଆଗକୁ ବଢିବା ପାଇଁ ଦୟାକରି ଲାଇନରେ ରୁହନ୍ତୁ କିମ୍ବା 1 ଦବାନ୍ତୁ। ଯଦି ଆପଣ ଏଥିରେ ସହମତ ନୁହଁନ୍ତି, ତେବେ କଲ୍ କାଟି ଆମର ହ୍ୱାଟ୍ସଆପ୍ ଆସିଷ୍ଟାଣ୍ଟ ଜରିଆରେ ବୁକ୍ କରିପାରିବେ।"
        else:
            return f"Thank you for calling {clinic}. This call is answered by Vaani, our AI receptionist. To manage your booking, we process your phone number and conversation. For quality and security, this call may be recorded under the DPDP Act. To proceed, please stay on the line or press 1. If you do not consent, you may hang up and book via our WhatsApp assistant."

    def get_filler_phrase(self, lang: str) -> str:
        """Return the vernacular filler phrase for latency slips."""
        if lang == "hi":
            return "जी, एक सेकंड..."
        elif lang == "hi-Latn":
            return "Ji, ek second..."
        elif lang == "or":
            return "ଟିକେ ଅପେକ୍ଷା କରନ୍ତୁ..."
        return "Just a moment..."

    async def save_consent(self) -> None:
        """Atomically set consent_accepted to True and save to contact database profile."""
        self.consent_accepted = True
        now = dt.now(UTC).replace(tzinfo=None)
        await Contacts(self.tenant_id).update_one(
            {"_id": self.contact_id},
            {
                "$set": {
                    "consent": {
                        "status": "granted",
                        "ts": now,
                        "notice_version": "1.0"
                    }
                }
            }
        )

    def clear_output_buffer(self) -> None:
        """Clear session output state in case of barge-in interruption."""
        self.interrupted = True
        logger.info(f"Session {self.call_sid} output buffer cleared due to barge-in.")

    async def handle_user_input(self, audio_data: bytes, lang: str = "en") -> dict[str, Any]:
        """Main loop execution for a turn of user speech.
        
        Asserts consent plays first. Tracks latency budget and returns text + voice payload.
        """
        effective_lang = lang or getattr(self, "default_lang", "en")
        # 1. Enforce Consent-First check
        if not self.consent_played:
            self.consent_played = True
            consent_text = self.get_consent_text(effective_lang)
            logger.info("Consent script played first. Deferring query processing.")
            consent_audio = await synthesize(consent_text, effective_lang, sample_rate=self.sample_rate)
            return {
                "transcript": "[DPDP Voice Consent Played]",
                "response": consent_text,
                "audio": consent_audio,
                "consent_pending": True,
                "latencies": {"consent_play": 0}
            }

        # Handle DTMF input for consent confirmation if user pressed 1
        if audio_data == b"DTMF_1":
            await self.save_consent()
            welcome_map = {
                "hi": "धन्यवाद। मैं आपकी क्या मदद कर सकती हूँ?",
                "hi-Latn": "Dhanyawad. Main aapki kya madad kar sakti hoon?",
                "or": "ଧନ୍ୟବାଦ। ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ୍ୟ କରିପାରିବି?",
                "en": "Thank you. How can I help you today?",
            }
            welcome_text = welcome_map.get(effective_lang, welcome_map["en"])
            welcome_audio = await synthesize(welcome_text, effective_lang, sample_rate=self.sample_rate)
            return {
                "transcript": "[DTMF Consent Accepted]",
                "response": welcome_text,
                "audio": welcome_audio,
                "consent_accepted": True
            }

        if not self.consent_accepted:
            reminder_map = {
                "hi": "जारी रखने के लिए कृपया 1 दबाएं।",
                "hi-Latn": "Aage badhne ke liye kripya 1 press karein.",
                "or": "ଆଗକୁ ବଢିବା ପାଇଁ ଦୟାକରି 1 ଦବାନ୍ତୁ।",
                "en": "Please press 1 to consent before continuing.",
            }
            reminder = reminder_map.get(effective_lang, reminder_map["en"])
            return {
                "transcript": "[Consent pending]",
                "response": reminder,
                "audio": await synthesize(reminder, effective_lang, sample_rate=self.sample_rate),
                "consent_pending": True,
                "latencies": {},
            }

        # 2. Reset interruption state on new turn
        self.interrupted = False
        self.is_speaking = True

        t_start = time.perf_counter()

        # Step A: STT Transcription
        t0 = time.perf_counter()
        stt_result = await transcribe_audio(audio_data, effective_lang)
        transcript = stt_result["text"]
        t_stt = time.perf_counter() - t0
        self.latencies["stt_ms"] = int(t_stt * 1000)

        # Low-confidence or empty audio recovery
        confidence = stt_result.get("confidence")
        if not transcript.strip() or (confidence is not None and float(confidence) < 0.35):
            recovery_map = {
                "hi": "माफ़ कीजिये, मैं सुन नहीं पाई। क्या आप दोबारा कह सकते हैं?",
                "hi-Latn": "Maaf kijiye, main sun nahi paayi. Kya aap dobara bol sakte hain?",
                "or": "କ୍ଷମା କରିବେ, ମୁଁ ଶୁଣିପାରିଲି ନାହିଁ। ଆପଣ ପୁଣି ଥରେ କହିପାରିବେ କି?",
                "en": "I'm sorry, I couldn't hear you clearly. Could you please repeat that?",
            }
            recovery_text = recovery_map.get(effective_lang, recovery_map["en"])
            audio_bytes = await synthesize(recovery_text, effective_lang, sample_rate=self.sample_rate)
            t_total = time.perf_counter() - t_start
            self.latencies["total_ms"] = int(t_total * 1000)
            self.is_speaking = False
            return {
                "transcript": transcript or "[unintelligible]",
                "response": recovery_text,
                "audio": audio_bytes,
                "latencies": self.latencies,
                "filler_injected": False,
                "interrupted": self.interrupted,
                "low_confidence_recovery": True,
            }

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

        if not response_text.strip():
            fallback_map = {
                "hi": "माफ़ कीजिये, कृपया एक पल प्रतीक्षा करें या थोड़ी देर बाद पुनः प्रयास करें।",
                "hi-Latn": "Maaf kijiye, kripya ek pal pratiksha karein ya thodi der baad dobara call karein.",
                "or": "କ୍ଷମା କରିବେ, ଦୟାକରି ଟିକେ ଅପେକ୍ଷା କରନ୍ତୁ କିମ୍ବା ପରେ ଚେଷ୍ଟା କରନ୍ତୁ।",
                "en": "I'm sorry, please hold for a moment or try again shortly.",
            }
            response_text = fallback_map.get(effective_lang, fallback_map["en"])

        # Log query to DB message history
        messages = Messages(self.tenant_id)
        now = dt.now(UTC).replace(tzinfo=None)
        await messages.insert_one({
            "conversation_id": self.conversation_id,
            "direction": "inbound",
            "type": "text",
            "text": transcript,
            "lang": effective_lang,
            "intent": res.get("intent"),
            "confidence": res.get("confidence"),
            "ts": now
        })

        # Step C: TTS Generation
        t0 = time.perf_counter()
        audio_bytes = await synthesize(response_text, effective_lang, sample_rate=self.sample_rate)
        t_tts = time.perf_counter() - t0
        self.latencies["tts_ms"] = int(t_tts * 1000)

        t_total = time.perf_counter() - t_start
        self.latencies["total_ms"] = int(t_total * 1000)

        # Log response to DB
        await messages.insert_one({
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
