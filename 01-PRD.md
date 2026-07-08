# PRD — Project Vaani: AI Front-Desk Agent for Indian SMBs

**Version:** 1.0 | **Date:** 07 Jul 2026 | **Owner:** Subham Jena (Xolver) | **Status:** Draft for validation

---

## 1. Problem Statement

Indian appointment-driven SMBs (clinics, salons, coaching institutes) miss 20–40% of inbound calls during peak hours, after hours, and while serving walk-ins. Every missed call is a lost booking worth ₹300–₹2,000+. Owners also spend 1–2 hours/day manually chasing payments and confirming appointments over WhatsApp. Hiring a receptionist costs ₹12,000–₹18,000/month and doesn't cover after-hours. There is no vernacular, compliance-safe, affordable AI front-desk product for this segment.

**Evidence required before build (Phase 0 gate):** 20 owner interviews confirming (a) ≥10 missed calls/day, (b) willingness to pay ₹2,999/month, (c) 5 signed pre-commitments.

## 2. Product Vision

Every Indian SMB hires an AI employee before it builds a website. Vaani is that first AI employee: it answers WhatsApp messages and phone calls in the customer's language, books appointments, sends reminders, collects payments, and hands off to the owner when it's out of its depth.

## 3. Target Users

**Primary persona — "Dr. Priya" (SMB Owner):** Runs a 1–3 practitioner dental clinic in a Tier-1/2 city. 30–80 inbound contacts/day across calls and WhatsApp. Uses WhatsApp Business app manually today. Not technical. Buys on ROI proof, not features. Decision cycle: 1–2 weeks.

**Secondary persona — "Ravi" (Clinic Staff):** Receptionist/assistant who handles overflow and escalations. Needs a dead-simple escalation inbox, not a new system to learn.

**End customer — "Patient/Client":** Calls or messages in Hindi, Odia, or Hinglish. Wants a booking or answer in under 2 minutes. Will not download an app.

**Vertical for v1: dental + general clinics only.** Salons and coaching institutes are v2 verticals (see Non-Goals).

## 4. Goals (v1, 6 months post-launch)

| # | Goal | Metric | Target | Stretch |
|---|------|--------|--------|---------|
| G1 | Prove revenue recovery for customers | Recovered bookings attributable to Vaani per customer/month | ≥20 | ≥40 |
| G2 | Achieve paying customer base | Paying customers | 25 | 50 |
| G3 | Retention | Monthly logo churn | <5% | <3% |
| G4 | Unit economics | Gross margin after AI + telephony + BSP costs | >60% | >70% |
| G5 | Containment | % of conversations resolved without human handoff | >70% | >85% |

## 5. Non-Goals (v1)

1. **General-purpose chat.** The agent answers ONLY scoped intents. This is both a product decision and a hard compliance requirement under Meta's Jan 2026 WhatsApp Business Platform policy (see Compliance doc §2).
2. **Multi-vertical support.** No salon/coaching flows in v1. One vertical = tighter prompts, better containment, clearer case studies.
3. **Outbound cold marketing / bulk broadcast.** Reputationally and policy risky. Only transactional/utility outbound (reminders, payment nudges) with opt-in.
4. **Native mobile app for owners.** Owner dashboard is a responsive web app. Expo app is a P2 after 25 paying customers.
5. **EHR/practice-management integrations.** No Practo/Docon sync in v1. Vaani maintains its own calendar; owner can also connect Google Calendar (P1).
6. **English-only or 10-language support.** v1 languages: Hindi, English, Hinglish (code-switched), Odia. Adding languages before nailing these four dilutes quality.
7. **Self-serve onboarding.** v1 is white-glove onboarding by Xolver. Self-serve is P2.

## 6. User Stories (priority order)

### Owner (Dr. Priya)
- **US-1 (P0):** As a clinic owner, I want every inbound WhatsApp message answered within 10 seconds so that I stop losing patients to competitors who reply faster.
- **US-2 (P0):** As a clinic owner, I want patients to book/reschedule/cancel appointments without my involvement so that I reclaim 1–2 hours/day.
- **US-3 (P0):** As a clinic owner, I want to see every conversation, booking, and payment in one dashboard so that I trust what the agent did.
- **US-4 (P0):** As a clinic owner, I want the agent to escalate to my phone (WhatsApp + missed-call alert) when it can't help so that no patient is left stranded.
- **US-5 (P1):** As a clinic owner, I want automated appointment reminders (24h and 2h before) so that no-shows drop.
- **US-6 (P1):** As a clinic owner, I want the agent to answer my phone line in Hindi/Odia so that missed calls become bookings even when I'm with a patient.
- **US-7 (P1):** As a clinic owner, I want payment links sent for consultation fees/deposits so that I collect money without asking awkwardly.
- **US-8 (P1):** As a clinic owner, I want a weekly WhatsApp summary (bookings made, revenue recovered, calls handled) so that I see ROI without opening a dashboard.
- **US-9 (P2):** As a clinic owner, I want to edit FAQs and services/prices myself so that I don't depend on Xolver for content changes.

### Staff (Ravi)
- **US-10 (P0):** As clinic staff, I want an escalation inbox showing conversations needing a human, with full context, so that I can take over in one tap.
- **US-11 (P1):** As clinic staff, I want to mark an escalation resolved and return the conversation to the agent so that automation resumes.

### End customer (Patient)
- **US-12 (P0):** As a patient, I want to message the clinic in Hindi/Odia/Hinglish and get an instant, correct answer about timings, services, fees, and location so that I don't have to call repeatedly.
- **US-13 (P0):** As a patient, I want to pick an appointment slot from real availability so that my booking is actually confirmed, not "we'll call you back."
- **US-14 (P0):** As a patient, I want to reach a human when I ask for one or have a complex/medical question so that I'm never stuck arguing with a bot.
- **US-15 (P1):** As a patient calling the clinic, I want the phone answered in my language with the option to book directly so that an engaged line doesn't cost me my slot.
- **US-16 (P1):** As a patient, I want to receive and pay a UPI payment link so that I can secure my slot.

### Edge cases (P0 acceptance coverage)
- Patient sends a voice note → transcribe and process as text; if transcription confidence low, ask to type or escalate.
- Patient asks a medical question ("is this infection serious?") → refuse to advise, offer booking + escalation. **Never** provide medical advice.
- Patient asks something out of scope ("what's the weather") → standardized out-of-scope reply + menu of what the agent can do (Meta compliance requirement).
- Double-booking race (two patients pick same slot) → second gets next-best slots; never confirm an unavailable slot.
- Owner's calendar is full → offer waitlist entry (P1) or next available day.
- Abusive user → one de-escalation attempt, then escalate and flag.
- Relative-date ambiguity ("kal" = yesterday OR tomorrow; "parso"; "agle hafte") → agent must always confirm the resolved date explicitly with weekday + date ("कल यानी मंगलवार, 14 जुलाई — ठीक है?") before booking. Never book on an unconfirmed relative date.
- Patient asks for directions / "kahan par hai" → send the clinic's saved WhatsApp location pin + landmark line (landmarks beat addresses in India), not a text-only address.
- Clinic closed for a festival/holiday (Raja, Rath Yatra, Diwali, regional bandh) → agent quotes the holiday closure from the tenant holiday calendar and offers the next open day; never offers slots on a closed day.
- Patient gives a missed call instead of messaging (common Indian behavior) → missed-call-to-WhatsApp bridge auto-initiates a WhatsApp conversation (P1, F-16).

## 7. Functional Requirements

### P0 — Must-Have (cannot ship pilot without)
| ID | Requirement | Acceptance criteria (summary) |
|----|-------------|-------------------------------|
| F-01 | WhatsApp inbound agent via BSP (Meta Cloud API) | Given a patient message in Hindi/English/Hinglish/Odia, when it maps to a scoped intent (FAQ, booking, reschedule, cancel, status, escalate), then the agent responds correctly in the same language within p95 ≤ 10s. |
| F-02 | Intent scope filter (compliance gate) | Given any out-of-scope input, the agent returns the standard out-of-scope template + capability menu; the LLM is never invoked in open-domain mode. 100% of responses pass a post-generation scope classifier before send. |
| F-03 | Appointment engine | Slot model per practitioner; book/reschedule/cancel with conflict prevention (atomic slot claim); confirmations sent on WhatsApp; owner calendar view; per-tenant holiday calendar (national + state/regional festivals, owner-editable) blocks slot generation on closed days. Zero double-bookings in testing (500 concurrent-booking simulation). |
| F-04 | Human handoff | Triggers: user asks for human; 2 consecutive low-confidence turns; medical/complaint intent; abusive content. On trigger: conversation paused for bot, staff notified on WhatsApp within 30s, escalation inbox shows full transcript. |
| F-05 | Owner web dashboard | Conversations list + transcripts, bookings calendar, escalation inbox, basic settings (hours, services, fees, FAQ text), daily counters. Mobile-responsive. |
| F-06 | Business knowledge base per tenant | Structured fields (hours, address, services, fees, doctors, policies) + free-text FAQs; agent answers ONLY from this KB via RAG; if answer not in KB → "I'll check with the clinic" + escalate. No hallucinated fees/timings (0 tolerance in UAT). |
| F-07 | Audit log | Every message, intent classification, tool call, and handoff logged immutably per tenant, retained 90 days (configurable), exportable. Required for Meta scope audits and DPDP. |
| F-08 | DPDP consent & notice | First-contact message includes purpose notice + link to privacy notice; consent state stored; data principal request handling process documented (see Compliance doc §3). |
| F-09 | Multi-tenant isolation | Tenant ID enforced at every query; cross-tenant data access impossible by construction (tested). |

### P1 — Nice-to-Have (fast follows, weeks 7–16)
| ID | Requirement |
|----|-------------|
| F-10 | Voice channel: inbound calls via SIP (Exotel/Plivo) → Indic STT → same agent core → Indic TTS. Latency budget: first audio response ≤ 2.0s, turn p95 ≤ 3.5s. Confidence-based handoff to owner's phone (warm transfer). |
| F-11 | Automated reminders: 24h + 2h pre-appointment via WhatsApp utility templates; reschedule from reminder. |
| F-12 | Payments: Razorpay payment links (UPI) for consultation fee/deposit; reconciliation in dashboard; payment nudge sequence (max 2 nudges). |
| F-13 | Weekly owner ROI summary on WhatsApp (bookings, estimated recovered revenue, containment rate). |
| F-14 | Google Calendar 2-way sync (owner-side availability). |
| F-15 | Waitlist + no-show recovery flow. |
| F-16 | Missed-call-to-WhatsApp bridge: patient gives the clinic a missed call → Vaani auto-opens a WhatsApp conversation ("Aapne call kiya tha — appointment book karna chahenge?") via approved utility template. Converts India's missed-call habit into bookings; also the cheapest patient-acquisition hook for the clinic ("miss call do, appointment pao" on the clinic board). Requires prior opt-in or existing-patient relationship per Meta policy. |
| F-17 | GST-compliant subscription invoicing for owners: auto-generated tax invoice (Xolver GSTIN, SAC code, 18% GST, clinic GSTIN if registered) emailed/WhatsApped monthly. SMB owners' accountants ask for this on day one. |

### P2 — Future (architectural insurance only; do not build)
- Self-serve onboarding & KB editor; owner Expo app; salon/coaching vertical packs; outbound invoice chasing for service SMBs; multi-branch support; analytics benchmarking across tenants (aggregated, anonymized, consent-gated).

## 8. Success Metrics & Measurement

**Leading (weekly):**
- Containment rate = resolved conversations / total conversations. Target >70% by week 8 of pilot.
- Booking conversion = bookings / booking-intent conversations. Target >60%.
- p95 response latency (WhatsApp ≤10s; voice turn ≤3.5s).
- Escalation SLA: staff notified ≤30s, first human response ≤10 min during business hours.
- Hallucination incidents (wrong fee/time/service stated): target 0; any incident = P0 bug.

**Lagging (monthly):**
- Recovered bookings/customer/month (G1) — measured as bookings created outside business hours + bookings created while line busy + bookings from previously-missed numbers.
- Logo churn <5%; NPS ≥ 40 at day 60; gross margin >60%.

**Measurement method:** all metrics computed from the audit log + bookings collection; dashboard "Metrics" page; weekly automated report. No metric may rely on manual counting.

## 9. Pricing (summary — full model in GTM doc)

- **Starter** ₹2,999/mo: WhatsApp agent, bookings, reminders, dashboard. Fair-use 1,000 conversations/mo.
- **Pro** ₹6,999/mo: + voice line (300 min/mo included, then ₹4/min), payments, ROI reports.
- **Outcome add-on:** ₹49 per confirmed booking above 50/mo (Starter) — aligns price to value, protects margin on heavy users.
- All prices exclusive of 18% GST; GST tax invoice auto-issued (F-17). Quote "₹2,999 + GST" everywhere — never let the first invoice surprise the owner.
- Pilot: 30 days free, UPI Autopay mandate on file (₹2,999 and ₹6,999 both sit under the ₹15,000 no-AFA autopay limit, so recurring debits run without per-charge approval), auto-converts.

## 10. Open Questions

| # | Question | Owner | Blocking? |
|---|----------|-------|-----------|
| Q1 | Meta moved WhatsApp to **per-message pricing (July 2025)**: service-window replies are free; utility templates inside the 24h window are free; only utility/auth templates outside the window are billed (~₹0.115/msg India, verify current rate card). Since most of Vaani's traffic is inbound-service replies, COGS may be materially lower than the old per-conversation model assumed. Verify BSP markup on top of Meta rates and re-run the TRD §7 margin math before pricing lock. | Subham | Yes — before pricing lock (Week 2) |
| Q2 | Sarvam vs Deepgram vs Google STT accuracy on Odia phone audio — needs bake-off with 50 real call recordings. | Eng | Yes — before Phase 2 |
| Q3 | Does clinic call recording require both-party notification in target states beyond DPDP notice? Confirm with counsel. | Legal | Yes — before voice launch |
| Q4 | Warm transfer vs blind transfer on Exotel for handoff UX? | Eng | No |
| Q5 | Is "recovered revenue" attribution methodology defensible enough for marketing claims (ASCI compliance)? | Subham | No |

## 11. Timeline Considerations

- No external hard deadline. Internal gates only (see Build Plan).
- Dependency: Meta Business verification + BSP number provisioning takes 1–6 weeks → **start Week 1**, in parallel with validation.
- Dependency: DPDP notice + consent flow must be legal-reviewed before first pilot message (Week 3 gate).
- Phasing: WhatsApp-first (Phase 1), voice second (Phase 2). Voice is the differentiator but WhatsApp is the faster proof of value.
