# User Flows — Project Vaani (End-to-End)

**Version:** 1.0 | **Date:** 18 Jul 2026 | **Owner:** Subham Jena (Xolver)
**Scope:** the complete message-level journey for every actor — customer, owner, staff — across WhatsApp, voice, and dashboard. For a WhatsApp product **the copy is the UI**, so flows are specified down to the actual messages. Requirements (F-xx) live in [01-PRD.md]; architecture in [02-TRD.md]; every flow here traces to a TDD loop in [07-tdd-loops.md] (§6).

---

## 0. Design Principles — what "Anthropic-grade" means for a receptionist

These are the product's constitution. Every template, flow, and refusal is reviewed against them; each is enforced somewhere in code or CI, not just aspired to.

| # | Principle | Enforcement |
|---|-----------|-------------|
| 1 | **Always an AI, never pretends.** Vaani introduces itself as an AI assistant in the first message and at every call open. No fake human persona, no artificial "human-like" typing delays — reply the moment the answer is ready. | First-contact template + voice open script; latency tests assert no injected delay |
| 2 | **Help first, paperwork second.** The consent notice never blocks the answer — disclosure and the useful reply travel in the same message. No "reply YES to continue" walls. | First-contact template design (P1); consent recorded via notice-version + continued use per DPDP notice |
| 3 | **Taps over typing.** Any choice that can be a button or list is one. Free text always works too — pickers are an offer, not a cage. | F-18; L6 ≤3-tap test |
| 4 | **Speed is respect; honest delay beats silence.** Seen ≤1s, reply p50 ≤3s, and if processing runs long, say so ("एक minute, check कर रही हूँ…"). Never silent >15s. | TRD §6 latency NFR; latency choreography (§5.2) |
| 5 | **Refuse warmly, always with a path.** Every refusal (restricted advice, out-of-scope) carries an alternative: a booking offer, a human, a menu. A dead end with no exit is a P1 bug. | Templates (P10, P11); graph topology test L7 |
| 6 | **Never guess a fact.** Fees, timings, addresses are KB-cited or the answer is "I'll check with the business" + escalation. Sounding sure beats being sure nowhere in this product. | Output gate; hallucination eval = 0 (L7) |
| 7 | **The customer's language, the customer's register.** Mirror language per message (hi/en/hi-Latn/or); आप/ଆପଣ always; colloquial time rendering ("5:00 PM — shaam"). | Lang-detect node; register grep test (L7) |
| 8 | **Attention is borrowed.** Quiet hours (21:00–08:00) for all proactive messages except customer-triggered confirmations; ≤2 payment nudges ever; opt-out line in every proactive template; no dark patterns — scarcity is only stated when literally true from slot data. | Template linter + scheduler rules; compliance self-audit |
| 9 | **Every dead end has a human exit.** "Staff" / "इंसान से बात" works from any state, including mid-booking, degraded mode, and voice. | `human_request` intent reachable from every graph state (test) |
| 10 | **Dignity in exit.** Cancelling a booking, opting out, or a business offboarding is one tap / one message, honored instantly, with data export offered. No guilt-trips, no retention traps. | Cancel flow (P4), offboarding flow (O8), DPDP pipeline |

---

## 1. Cast & Surfaces

| Actor | Surface | Flows |
|-------|---------|-------|
| **Customer** (Hindi/Odia/Hinglish/English; will not install anything) | WhatsApp chat; phone call (Phase 2) | P1–P17 |
| **Owner** (Dr. Priya — buys on ROI, lives on WhatsApp + phone browser) | WhatsApp (alerts, ROI summary, onboarding); dashboard | O1–O8 |
| **Staff** (Ravi — needs one tap, not one system) | WhatsApp alert → escalation inbox | S1 |
| **Vaani** | Named AI assistant; female-voiced "वाणी" (= "voice/speech"); always labeled "AI सहायक" | all |

---

## 2. Customer Journey

Master map — every path lands in a terminal state that is either **resolved**, **booked**, or **with a human**. There is no state where the customer is stuck with the bot.

```
 discover (business board / missed call / saved number / reminder)
    │
    ▼
 P1 first contact ──► P2 booking ──► P8 reminder ──► visit ──► P13 CSAT
    │                    │                │
    ├─► P5 FAQ           ├─► P9 payment   └─► P4 reschedule/cancel ─► backfill
    ├─► P10 restricted ─┐   └─► P3 rebook (next time)
    ├─► P11 o-o-s    ├──► P12 human handoff ──► resolve & return
    └─► P14 abuse ───┘
```

### P1 — First contact (the 10-second trust window)

New contact sends anything (e.g. *"kal appointment milega?"*). One reply does three jobs — disclose, notice, help — in that order of brevity:

> **Vaani:** नमस्ते! 🙏 मैं **वाणी** हूँ — {business_name} की AI सहायक। appointment, समय और फ़ीस में मदद कर सकती हूँ; कभी भी *"staff"* लिखकर टीम से बात करें। *(आपकी जानकारी सिर्फ़ appointment के लिए — विवरण: {notice_link})*
>
> जी, कल यानी **शनिवार, 19 जुलाई** के लिए {staff_name} के ये slot खाली हैं: 👇
> `[List: 10:30 AM (subah) · 11:15 AM · 5:00 PM (shaam) · और slots →]`

Rules: intro block appears **once per contact** (re-sent only on notice-version bump); the customer's actual question is answered in the same message — the greeting never costs a turn. Language of the whole reply mirrors the inbound. Consent state + notice version recorded (F-08).

### P2 — Booking happy path (≤3 taps after intent)

1. Intent detected (typed or via menu) → relative-date resolver runs → **date echoed with weekday for confirmation inside the slot offer** ("कल यानी शनिवार, 19 जुलाई") — the confirmation and the picker are one message, not two turns.
2. **Tap 1:** customer picks a slot from the list (top 8 by relevance: requested time-of-day first, then proximity; "और slots →" pages).
3. Slot held atomically (120s) → confirm card:
   > **शनिवार, 19 जुलाई · शाम 5:00 बजे** · {staff_name} · {service} (₹500)
   > `[✅ पक्का करें] [🔄 बदलें] [❌ रहने दें]`
4. **Tap 2:** ✅ → booked. Confirmation message = booking card + **location pin + landmark line** ("Bapuji Nagar मंदिर के सामने") + "24 घंटे पहले reminder भेज दूँगी। बदलना हो तो यहीं message करें।"

Branches: hold expires → "यह slot अभी-अभी भर गया 😔 ये सबसे नज़दीकी options हैं:" + fresh list (never a false confirm — race-safe by construction); no slots that day → next open day offered + waitlist opt-in; business closed (festival) → "उस दिन क्लिनिक **रथ यात्रा** के लिए बंद है — अगला खुला दिन सोमवार:" + list. First name asked **only at first booking**, once: "किस नाम से बुक करूँ?" — never a form.

### P3 — Returning customer / one-tap rebook (F-20)

Known contact, booking intent →
> नमस्ते Ravi जी! पिछली बार की तरह — **{staff_name}, {last_service}**? `[हाँ, वही] [कुछ और]`
"हाँ" → slot list pre-filtered to their usual time-of-day. Two taps total. Memory is visible but never presumptuous: preferences pre-fill, they never auto-book.

### P4 — Reschedule / cancel → auto-backfill (F-22)

"Cancel/postpone" or reminder-button tap → current booking card + `[🔄 नई तारीख़] [❌ Cancel करें]`. Cancel = **one tap, honored instantly**, no "are you sure" double-gates, no guilt copy: "ठीक है, cancel कर दी। जब ज़रूरत हो, message कर दीजिएगा 🙏"
→ **Backfill fires:** waitlisted customers for that staff member/day get: "एक slot खाली हुआ है — **आज शाम 5:00**। लेंगे?" `[हाँ! ] [नहीं]` — first tap wins the atomic hold; others get "slot भर गया, आप waitlist पर बने हुए हैं।" Cancelled revenue refills itself within minutes.

### P5 — FAQ (hours / fees / services / staff / location)

KB-grounded one-liners, answer-first, no preamble. Location gets **pin + landmark, never a text address** (F-06, PRD edge case). Fee answers always state what the fee covers ("Consultation ₹500 — X-ray अलग से")। KB miss → principle 6: "यह मुझे ठीक-ठीक नहीं पता — हमारी टीम से पूछकर बताती हूँ 🙏" + escalation (customer never re-asks; staff answer returns through the same thread).

### P6 — Voice note in

Transcribe → confidence ≥0.75 → treat as text (reply is **text**, not voice — WhatsApp voice replies are intrusive in public). Below threshold: "आवाज़ साफ़ नहीं आई 😔 type कर देंगे, या staff से बात कराऊँ?" `[Type करूँगा] [Staff]`

### P7 — Missed call → WhatsApp bridge (F-16)

Customer gives the business a missed call (opt-in/existing relationship gated) → within 60s, utility template:
> आपने {business_name} को call किया था 🙏 line व्यस्त थी — मैं वाणी, हमारी AI सहायक। appointment book करूँ? `[हाँ, slot दिखाओ] [बाद में]`
"बाद में" is respected — no follow-up nudge. India's missed-call habit becomes a booking without a redial.

### P8 — Reminders (F-11)

T-24h: booking card + `[✅ आऊँगा] [🔄 बदलें] [❌ Cancel]` · T-2h: one line + pin. Confirm-tap feeds no-show data; 🔄 jumps straight into P4's picker. Both are utility templates; quiet-hours shifted (a 7 AM appointment's 2h reminder sends at 8:00, flagged "aaj subah").

### P9 — Payment link (F-12)

Offered when the business requires deposit / customer asks to pay: Razorpay UPI link + amount + what it's for + "पर्ची (receipt) यहीं मिल जाएगी।" Paid → instant confirmation + receipt. Unpaid → max 2 nudges, then silence (principle 8). Payment **never blocks** a booking unless the business's policy requires deposit — and then the copy says so plainly.

### P10 — Restricted-advice question (hard-templated, urgency-aware)

*Shown for a business whose profile restricts medical advice. The topics come from the tenant's `business_profile`; a salon, for example, would restrict skin-treatment advice instead.*

*"daant me bahut dard hai, koi dawa batao"* →
> मैं दवा या इलाज की सलाह नहीं दे सकती — यह हमारी टीम ही ठीक बता पाएगी 🙏 दर्द ज़्यादा है तो **आज का सबसे पहला slot** दिला सकती हूँ, या अभी staff से बात कराऊँ?
> `[आज का पहला slot] [Staff से बात]`
The refusal is one line; the help is the rest. Pain/urgency keywords bump the offer to earliest-available. Escalation flag set silently for staff context. LLM never generates this path (graph topology, L7).

### P11 — Out of scope

Static template + capability menu (Meta compliance): "मैं इसमें मदद नहीं कर पाऊँगी 🙏 मैं ये कर सकती हूँ:" `[📅 Appointment] [🕐 समय/फ़ीस] [📍 पता] [👤 Staff से बात]` — no lecture, no apology paragraph, straight to what works.

### P12 — Human handoff (customer view)

Trigger (asked / 2× low-confidence / restricted advice / complaint / abuse) →
> मैं आपको हमारी टीम से जोड़ रही हूँ — business hours में 10 मिनट के अंदर जवाब मिलेगा 🙏
Sets expectation honestly (out-of-hours: "कल सुबह 9 बजे से team उपलब्ध है — तब तक appointment मैं book कर सकती हूँ")। Bot goes silent in-thread; staff replies arrive in the same chat (no new number, no ticket ID — the customer sees one continuous conversation). After staff resolves → bot resumes silently with context (P13 fires).

### P13 — CSAT (F-21)

On resolution, once per conversation: "क्या मैं मदद कर पाई? `[👍] [👎]`" — one line, no stars, no survey. 👎 → "बताना चाहें तो लिखिए — team तक पहुँचा दूँगी 🙏" + auto eval-candidate + owner digest entry. Never re-asked in the same conversation; never sent after abuse flows.

### P14 — Abuse

One de-escalation, no moralizing: "मैं मदद के लिए हूँ 🙏 कुछ ग़लत हुआ है तो बताइए, या staff से बात करा दूँ।" Second instance → silent escalate + flag. Vaani never argues, never matches tone, never threatens ("this conversation is being recorded" style copy is banned).

### P15 — Data rights (DPDP)

"मेरा data delete karo" (or notice-link path) → template: rights summary + grievance contact + "आपकी request हमारी टीम तक पहुँचा दी है — 7 दिन में पूरी होगी।" → escalation to owner + `dpdp_delete` pipeline + audit. Exercising a right is a first-class flow, not a buried link.

### P16 — Voice call (Phase 2)

1. Answer ≤2 rings: "नमस्ते, {business_name}! मैं वाणी, AI सहायक बोल रही हूँ — यह call quality के लिए record हो सकती है। बताइए?" (disclosure + consent + invitation in ≤6 seconds, then silence — the caller talks first from here).
2. Same graph, voice register: shorter sentences, one question at a time, numbers repeated ("शाम पाँच बजे — 5 PM")। Date confirmations always echoed (same `date_confirmed` contract).
3. Barge-in always on — the caller can interrupt any sentence. Two misunderstandings → "मैं आपको सीधे हमारे number पर मिलाती हूँ" (warm transfer); unreachable → voicemail-to-task + WhatsApp follow-up if the number is on WhatsApp ("call के लिए धन्यवाद — यहाँ भी book कर सकते हैं 👇").
4. Booking confirmed on call → WhatsApp confirmation card sent too (paper trail principle).
5. Very noisy line → DTMF: "appointment के लिए 1 दबाएँ…"

### P17 — Degraded mode (the flow nobody plans; we do — TRD §9)

LLM down → menu mode. Honest, small, functional:
> अभी मुझे थोड़ी technical दिक्कत है, पर appointment के काम चल रहे हैं 👇
> `[📅 Book करें] [🕐 समय/फ़ीस] [👤 Staff]`
Picker + deterministic tools complete bookings with zero LLM. Free-text gets: "अभी मैं सिर्फ़ इन buttons से मदद कर पा रही हूँ 🙏" Recovery is silent — no "we're back!" spam.

---

## 3. Owner Journey

### O1 — Demo (the missed-call closer, GTM §4)

At the business: owner gives their own business a missed call from a spare phone → watches P7 fire → books a fake appointment through P2 on their own number → sees it land in a demo dashboard. **The product demos itself in its own medium in under 3 minutes.** Close: "यही आपके हर customer के साथ होगा — कल से।"

### O2 — Onboarding hour (F-23; the demo *is* the onboarding)

LOI signed → same day:
1. Vaani scrapes Google Business Profile + website (+ price-list photo OCR) → draft KB.
2. Owner receives the KB **as WhatsApp approve/edit cards** — "Consultation fee **₹500** — सही है? `[✅] [✏️ बदलें]`" — one card per fact (hours, fees, services, staff, landmark, holidays; Odisha festival calendar pre-seeded for review). ~15 cards, ~10 minutes.
3. Schedules loaded from a photo/voice-note of the appointment book if that's what exists (meet the business where it is).
4. **Owner plays customer:** guided test conversation on the live number — they experience P1→P2 exactly as their customers will. This is deliberate: the owner's trust in the agent is built the same way the customer's is.
5. Go-live checklist: number on the business board ("miss call करें, appointment पाएँ"), staff trained (30 min = S1 walkthrough only).

### O3 — Activation window (day 0–3, goal G7)

Day 1 morning: "वाणी live है 🎉 पहली booking होते ही बताऊँगी।" First organic booking → the **activation moment**: "🎉 पहली booking वाणी ने खुद संभाली — Ravi जी, कल शाम 5 बजे। आपने कुछ नहीं किया — यही plan है 😊" No booking by 72h → intervention flow (auto-diagnostic: KB gaps? number publicized? staff intercepting calls?) surfaced to Xolver, not dumped on the owner.

### O4 — Daily & weekly rhythm

Daily (optional, default on, one message max): "आज: 12 conversations · 5 bookings · 1 आपकी team ने संभाली।" Weekly ROI summary (F-13) — the renewal engine:
> इस हफ़्ते वाणी ने: **84** customers को जवाब दिया · **31** appointments book कीं — जिनमें **9 बिज़नेस बंद होने के बाद** ≈ **₹8,500 recovered** · CSAT 4.6 ⭐ · [Dashboard] · *किसी बिज़नेस-मित्र को Vaani चाहिए? 1 महीना दोनों को free — [share करें]*
Every number traces to the audit log (ASCI rule); the referral line rides the message owners already screenshot into their WhatsApp groups.

### O5 — Escalation alert (mirror of P12)

Staff-first routing; owner alerted if staff misses the 10-min SLA: template with customer name, last message, one-tap deep link to the inbox thread. Never more than one alert per escalation per person.

### O6 — Trial → paid (day 25–30)

Day 25: honest summary — value delivered vs. price: "30 दिन में ₹31,400 की recovered bookings · plan ₹2,999 + GST/माह · autopay 1 अगस्त से — कुछ न करें तो अपने-आप चालू; बंद करना हो तो `[रोक दें]`।" **The cancel button is right there in the conversion message** (principle 10) — confidence, not capture. Paid → GST invoice auto-delivered (F-17). Day 45 → Sean Ellis one-tap survey.

### O7 — Dashboard (jobs, not features)

Four jobs, in priority order: **(1)** "What is Vaani saying right now?" → live conversations + transcripts (trust); **(2)** "Who needs a human?" → escalation inbox (S1); **(3)** "What's my day?" → bookings calendar; **(4)** "Is it worth it?" → metrics page = same numbers as the weekly summary, never a different story. Settings/KB edits are rare-path (owners edit via WhatsApp cards, O2-style, even post-launch — US-9).

### O8 — Offboarding (dignity in exit)

"बंद करना है" → one confirmation → autopay mandate cancelled same day, agent answers through the paid period, then the number reverts. Full data export (transcripts, bookings, contacts CSV) delivered unasked. Goodbye message thanks them and leaves the door open. No retention call scripts, no "are you sure" loops. Ex-customers who were treated well are the referral channel's silent partner.

---

## 4. Staff Journey (S1 — one tap, not one system)

1. Escalation fires → Ravi's WhatsApp: customer name + reason + last 2 messages + `[💬 जवाब दें]` deep link.
2. Link opens the inbox thread (phone browser, no login friction — magic-link JWT): full transcript above, reply box below. **Context is pre-read for them:** a one-line agent summary sits at the top ("दर्द की complaint, आज का slot चाहती हैं — मैंने अभी तक slot नहीं दिया")।
3. Ravi replies (his messages go out under the business's number, labeled internally as staff) → resolves → `[✅ हो गया, वाणी को वापस दो]`.
4. Bot resumes with the resolution summary in memory — the customer never re-explains. SLA timers visible per escalation; missed SLA → owner alert (O5).

---

## 5. Cross-Flow Rules

### 5.1 Language & register
Mirror the language of **each inbound message** (customers code-switch mid-conversation; Vaani follows). Register: आप/ଆପଣ always; emoji budget ≤1/message, 🙏 for refusals/apologies only; no ALL-CAPS, no exclamation stacking. Times rendered "5:00 PM (shaam)"; dates always weekday + date. Scripts never mixed within a sentence.

### 5.2 Latency choreography (what the customer feels)
`0s` webhook ack → `≤1s` blue tick + typing indicator ("seen") → `≤3s p50` reply → `>5s` typing persists (honest — we are working) → `>10s` interim message "एक minute, check कर रही हूँ…" → `15s` hard ceiling: reply, interim, or escalate — **silence past 15s is a P0 bug.** No artificial delays ever (principle 1).

### 5.3 Proactive-message etiquette
Only utility templates tied to a consent-linked transaction; quiet hours 21:00–08:00 (shifted, not skipped); every proactive template carries opt-out ("आगे reminder न चाहें तो 'STOP' लिखें"); STOP honored instantly and confirmed once; ≤2 nudges per payment, 0 re-asks after "बाद में."

### 5.4 Error & empty states
Every failure state has copy — "no slots," "hold expired," "payment failed," "transcription unclear," "degraded mode" — written and translated ×4 up front, not improvised by the LLM (they're templates, so they can't be hallucinated). Unknown internal error → P17 menu + auto-escalation, never a stack-trace apology.

---

## 6. Traceability — flow → requirement → test loop

| Flow | Requirements | TDD loop (07-tdd-loops.md) |
|------|--------------|---------------------------|
| P1 | F-01, F-08 | L4, L7, L10 |
| P2 | F-01, F-03, F-18 | L5, L6, L7 |
| P3 | F-20 | Phase-3 micro-loop |
| P4 | F-03, F-15, F-22 | L5; Phase-3 micro-loop |
| P5 | F-06 | L7 |
| P6 | edge case (PRD §6) | L4 |
| P7 | F-16 | Phase-3 micro-loop |
| P8 | F-11 | Phase-3 micro-loop |
| P9 | F-12 | Phase-3 micro-loop |
| P10, P11, P14 | F-02, F-04 | L7 (topology), L8 |
| P12, S1 | F-04, F-05 | L8, L9 |
| P13 | F-21 | L11 |
| P15 | F-08, DPDP | L10 |
| P16 | F-10 | L14–L16 |
| P17 | TRD §9 | L6, L12 |
| O1–O3 | F-23, G7 | L13 |
| O4, O6 | F-13, F-17 | Phase-3 micro-loops |
| O7 | F-05 | L9 |

**Copy source of truth:** all templates in this doc are v1 drafts; canonical versions live in `app/agent/templates/` ×4 languages, and every change to them re-runs the register/completeness tests (L7). This doc is updated when templates change — flows and copy never drift apart silently.
