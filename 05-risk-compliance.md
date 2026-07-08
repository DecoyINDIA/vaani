# Risk Register & Compliance Plan — Project Vaani

**Version:** 1.0 | **Date:** 07 Jul 2026

---

## 1. Risk Register

Scoring: Likelihood (L) and Impact (I) 1–5. Exposure = L×I. Review monthly; owner = Subham unless noted.

| ID | Risk | L | I | Exp | Mitigation | Trigger/response |
|----|------|---|---|-----|------------|------------------|
| R1 | Meta policy enforcement flags the bot (scope creep, template misuse) → throttling/suspension | 2 | 5 | 10 | Closed intent set + dual scope gates in code; monthly transcript self-audit; BSP relationship; utility templates only | Any Meta warning → freeze deploys, audit 500 transcripts, remediate within 72h |
| R2 | Vernacular accuracy insufficient (Hinglish/Odia, noisy phone audio) → low containment, churn | 4 | 4 | 16 | STT bake-off on real corpus before committing; eval suite per language; DTMF fallback on voice; human handoff always available | Containment <45% at wk 8 → feature freeze, quality-only sprint (Build Plan G1) |
| R3 | Unit economics break (Meta conversation pricing, LLM costs, voice ₹/min) | 3 | 4 | 12 | Per-tenant cost telemetry from day 1; overage billing in plans; model tiering (small model for classification); quarterly pricing re-verification | Any tenant GM <40% → fair-use enforcement or plan move; portfolio GM <55% → price rise |
| R4 | SMB churn after novelty wears off | 4 | 4 | 16 | Weekly ROI summary (makes value visible); reminders/payments features tie into revenue not just convenience; autopay mandates | Churn >10%/mo → diagnosis sprint per Build Plan G3 |
| R5 | Hallucinated fee/timing/medical content harms a patient or clinic | 2 | 5 | 10 | KB-grounding with citation requirement; output gate; medical intent hard-templated; 0-tolerance bug class; insurance review (professional indemnity) at 25 customers | Any incident → same-day RCA, affected-clinic call, eval case added |
| R6 | Founder bandwidth: Vaani vs Xolver services vs LawFlow | 4 | 4 | 16 | Time-boxed phases with kill gates; white-glove onboarding capped at ≤3h/clinic by Month 4; say no to custom work <₹25K | Slip >2 wks on any gate → cut scope, not extend timeline |
| R7 | Copycat competition (agencies wrapping same APIs) | 3 | 3 | 9 | Moats: vernacular eval corpus, compliance posture, case studies, vertical depth. Speed to 25 references matters more than features | Competitor in-market → double down on referral loop + case studies, don't feature-race |
| R8 | Telephony/BSP vendor outage or account issue | 2 | 4 | 8 | Fallback vendor pre-integrated for LLM (OpenRouter) and researched for telephony (Plivo); WABA hygiene (quality rating monitoring) | Quality rating drops → pause proactive templates, audit opt-ins |
| R9 | DPDP complaint or data incident | 2 | 5 | 10 | See §3; India-region storage, encryption, deletion pipeline, breach runbook | Incident → breach runbook, counsel, Data Protection Board notification if required |
| R10 | Clinic staff sabotage/non-adoption (job-threat perception) | 3 | 3 | 9 | Position as "staff assistant" not replacement in onboarding; staff owns escalation inbox (they gain a tool, not lose a job) | Staff not responding to escalations → owner conversation, adjust routing |

## 2. Meta / WhatsApp Business Platform Compliance (2026 policy)

**Rule:** general-purpose AI chatbots are prohibited on the WhatsApp Business Platform (effective for all accounts since 15 Jan 2026). Task-specific business bots (support, bookings, order status, notifications) are permitted. AI must be ancillary to the business service, not the product being distributed.

**Vaani's compliance-by-design controls:**
1. **Closed intent taxonomy** (TRD §4.1) — the agent cannot enter open-domain conversation; out-of-scope inputs get a static template. Enforced in code (dual gates), not prompt-only.
2. **No open LLM passthrough** — responder only runs for whitelisted intents with KB/tool grounding.
3. **Template discipline** — outside the 24h service window, only approved utility templates; no marketing category in v1; template quality/rating monitored weekly.
4. **Opt-in hygiene** — proactive messages (reminders, payment links) only to contacts with recorded consent tied to a booking/transaction.
5. **Auditability** — immutable per-message log incl. intent + gate decisions; monthly self-audit of 50 random transcripts against taxonomy; results filed in this register.
6. **BSP-only access** — no unofficial libraries, no number rotation, single verified WABA per deployment.
7. **Change control** — any new intent added to taxonomy requires a compliance note (is it a business task? is a template needed?) before release.

**Residual risk:** Meta's enforcement detection mechanics are not publicly documented; conservative posture above is the mitigation. Monitor BSP advisories monthly.

## 3. DPDP Act Compliance Plan

Vaani processes personal data (names, phone numbers, health-adjacent booking context, call recordings) as a **Data Processor for clinics (Data Fiduciaries)** — contractually defined in the customer agreement; Xolver is Fiduciary only for its own customer data.

**DPDP Rules 2025:** the Rules were notified in late 2025 with phased effect — consent-notice format, breach-notification mechanics, and retention obligations phase in over ~12–18 months from notification, which lands squarely inside Vaani's first operating year. Counsel task (Week 2): map each Rule's effective date to the compliance calendar below so obligations activate on schedule, and confirm whether clinic patient data triggers any Significant Data Fiduciary analysis for the clinics themselves (talking point for the sales one-pager, since clinics will start hearing about DPDP from their own advisors).

| Obligation | Implementation | Status/owner |
|------------|----------------|--------------|
| Notice & consent | First-contact notice message (purpose, categories, rights, grievance contact) in user's language; consent state per contact with notice version; voice: recorded consent line at call start | Copy drafted Wk 1; counsel review Wk 2 gate |
| Purpose limitation | Data used only for booking/support/payment per clinic instructions; no cross-tenant training or profiling; no ads use | Architecture-enforced; stated in DPA |
| Data minimization | Collect only phone, name, booking details; no health condition free-text stored beyond conversation log; media auto-purged at 30d | TRD data model |
| Storage & security | India region (ap-south-1), TLS, phone-number field encryption, access controls, secrets management | TRD §6 |
| Retention & erasure | 90d default log retention (clinic-configurable); deletion pipeline for data principal requests, SLA ≤7 days; deletion cascades incl. backups per schedule | Build Phase 1 |
| Data principal rights | Request intake via grievance contact published in notice; access/correction/erasure runbook | Runbook by pilot start |
| Processor contract (DPA) | Customer agreement includes DPA: instructions, sub-processor list (Atlas, OpenRouter models, BSP, Exotel, Razorpay, STT/TTS vendors), breach notification ≤72h to clinic | Template with counsel Wk 2 |
| Sub-processor diligence | Record each vendor's data-handling terms; prefer zero-retention LLM API flags; document in sub-processor register | Wk 3 |
| Breach response | Runbook: contain → assess → notify clinics ≤72h → Data Protection Board notification if thresholds met → RCA | Drafted before pilot |
| Call recording law (Q3) | Confirm state-level notification requirements beyond DPDP notice with counsel before voice launch | Blocking for Phase 2 |
| Children's data | Clinics may book for minors via guardians; guardian is the contact; no direct processing of minors' contact data; noted in DPA | Policy line |

**Selling point, not just compliance:** the one-pager "How Vaani protects your patients' data" is a sales asset (GTM §6). Regulatory posture is part of the moat — generic wrappers won't do this work.

## 4. Other Legal/Commercial Items

- **Customer agreement:** subscription terms, DPA, SLA (best-effort pilot; 99.5% from paid), liability cap = 3 months' fees, no medical-advice disclaimer, clinic responsible for KB accuracy (fees/timings they provide).
- **Telecom compliance:** use licensed operator (Exotel) numbers only; no TRAI-violating outbound voice marketing; transactional voice only. If SMS is ever added as a fallback channel, TRAI DLT registration (entity + template + header) is mandatory before the first message — currently out of scope, noted so it isn't discovered mid-sprint.
- **Telemedicine Practice Guidelines (2020):** Vaani never provides medical advice, triage, or prescriptions (hard-templated refusal, PRD §6 edge cases), so it stays outside the RMG/telemedicine regulatory perimeter. State this explicitly in the customer agreement and the sales objection sheet — clinic owners will ask.
- **GST:** Xolver GST registration confirmed for SaaS supply (SAC 998313/998314 — confirm with CA); e-invoicing threshold monitoring; auto-issued tax invoices per PRD F-17. Clinics claiming input credit is a quiet selling point ("effectively 18% cheaper for GST-registered clinics").
- **ASCI/claims:** marketing ROI claims must trace to audit-log-derived numbers with stated methodology.
- **IP:** agent core, eval corpus, and prompts owned by Xolver entity; contractor agreements assign IP; consider separate entity for Vaani at 25 customers (clean cap table for spin-out/raise).
- **Insurance:** professional indemnity + cyber quote at 25 customers.

## 5. Compliance Calendar

| Cadence | Action |
|---------|--------|
| Weekly | Template quality rating check; per-tenant cost/GM review |
| Monthly | 50-transcript scope self-audit; risk register review; sub-processor register update |
| Quarterly | Meta/BSP policy re-read; pricing/margin re-verification; DPDP runbook drill; restore drill |
| Event-driven | Any Meta warning, DPDP request, or hallucination incident → logged here with RCA |
