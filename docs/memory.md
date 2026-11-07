# PATIENT MEMORY SYSTEM SPECIFICATION — PROJECT VAANI

> **Production status as of 6 November 2026:** This specification describes intended behavior. The [production review](production-review.md) found ID/reference failures, shared voice caller identity/consent, and an unimplemented erasure workflow. Follow R03, R07, and R15 in the [remediation plan](production-remediation-plan.md) before relying on this behavior with real patient data.

This document defines the architecture, data models, and product flows for **Short-Term Session Memory** and **Long-Term Patient Memory** in Vaani.

---

## 1. Memory Architecture Overview

Vaani separates memory into two distinct scopes to balance LLM token economics, context correctness, and personalization:

```
                  ┌──────────────────────────────────────────────┐
                  │              PATIENT UTTERANCE               │
                  └──────────────────────┬───────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │            LANGGRAPH ROUTER             │
                    └──────┬──────────────────────────┬───────┘
                           │                          │
      ┌────────────────────▼─────┐      ┌─────────────▼────────────────┐
      │   SHORT-TERM SESSION     │      │      LONG-TERM PATIENT       │
      │        (Checkpointer)    │      │         (MongoDB Profile)    │
      ├──────────────────────────┤      ├──────────────────────────────┤
      │ • Message history (5 turns)│      │ • Greet by name ("Ravi Ji")  │
      │ • Active booking slots   │      │ • Doctor preference (Sharma) │
      │ • Active slot hold timers│      │ • Last service (cleaning)    │
      │ • Staff resolution summary│     │ • average CSAT score         │
      └──────────────────────────┘      └──────────────────────────────┘
```

---

## 2. Short-Term Session Memory

Short-term memory manages active dialog threads, transaction state, and conversation checkpoints.

*   **Technology:** LangGraph checkpointer backed by Redis (Mumbai) for ephemeral state and MongoDB for persistent conversation threads.
*   **Context Window Control:** To maintain p50 latency under 3 seconds, we cap the active message context sent to the generator at the **last 5 turns** (10 messages).
*   **Resolution Memory Injection:** 
    *   When staff resolves an escalation and clicks "Resolve & Return," they provide a resolution summary.
    *   This summary is written as a system message in MongoDB and injected at the top of the message context for the next turn.
    *   *System Prompt Injection:*
        `"Additional Context: Staff has just returned the conversation. Resolution summary: {{resolution_summary}}. Acknowledge this resolution context gracefully if the patient follows up."`

---

## 3. Long-Term Patient Profile Memory

Long-term memory persists patient history across conversations to enable rapid, low-friction interactions.

*   **Database Schema:** Stored in the `contacts` collection under the `profile` document:
    ```json
    {
      "_id": "contact_id",
      "tenant_id": "tenant_id",
      "wa_id": "whatsapp_id",
      "phone": "919999999999",
      "name": "Ravi Mohanty",
      "lang_pref": "or",
      "consent": {
        "status": "granted",
        "ts": "2026-07-18T18:00:00Z",
        "notice_version": "1.0"
      },
      "profile": {
        "preferred_practitioner_id": "practitioner_id",
        "last_service": "Tooth Extraction",
        "last_visit": "2026-04-12T10:30:00Z",
        "visit_cadence_days": 180,
        "csat_avg": 4.8
      }
    }
    ```

### Memory Update Mechanics (Write Pipe)
1.  **CSAT Score:** Calculated dynamically as a running average upon feedback receipt (`T_CSAT_REQUEST`).
2.  **Service History:** Automatically updated by the booking engine worker when a slot moves to `status: completed`.
3.  **Language Preference:** Captured during `lang_detect` and saved.
4.  **DPDP Consent (voice):** Written by `VoiceSession.save_consent()` in [session.py](file:///d:/XOLVER/Vaani/app/channels/voice/session.py) — on explicit DTMF-1 accept, or on the caller continuing the call past the consent notice — persisting `consent.status`, `consent.ts`, and `consent.notice_version` to the contact document per the schema above. A returning caller with `consent.status == "granted"` skips the consent replay on the next call. Prior to this, voice calls could reach transcription/storage without ever recording consent; see [handoff.md](file:///d:/XOLVER/Vaani/docs/handoff.md) §9.

---

## 4. Product Experience & One-Tap Rebooking (F-20)

Long-term profile memory is exposed to the patient to minimize typing friction:

### A. Greeting by Name
If a contact is found in the database with a populated `name` and active consent:
*   *Hinglish Prompt Output:* *"Namaste Ravi Ji! Vaani here from Sharma Dental Clinic..."* (adds the respectful indicator `Ji` automatically).

### B. One-Tap Rebook Flow
When a returning patient expresses booking intent:
1.  **Preference Detection:** The `responder` node checks `contacts.profile.preferred_practitioner_id` and `last_service`.
2.  **Interactive Offer:**
    *   *System Message:* *"Namaste Ravi Ji! Would you like to book a **Tooth Extraction** with **Dr. Sharma** (like last time)?"*
    *   *Interactive Buttons:* `[Yes, same]` `[No, something else]`
3.  **Fast Path:** Clicking `[Yes, same]` immediately bypasses practitioner/service selection and shows the doctor's upcoming 3 slots. The booking is completed in **2 taps** (Tap 1: slot selection, Tap 2: confirmation).
