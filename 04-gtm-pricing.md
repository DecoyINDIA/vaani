# GTM & Pricing Plan — Project Vaani

**Version:** 2.0 | **Date:** 18 Jul 2026

---

## 1. Positioning

**One-liner:** "Your clinic's AI receptionist — answers every call and WhatsApp in Hindi, Odia or English, books appointments, and never takes a day off. ₹2,999/month."

**Time-to-wow:** live on the clinic's own number, answering real patients, within 24 hours of "yes" — the demo *is* the onboarding (KB auto-draft, F-23). "Watch it answer your patients tomorrow" is a claim competitors doing 2-week flow-builder setups cannot match.

**Against alternatives:**
| Alternative | Their weakness | Our wedge |
|-------------|----------------|-----------|
| Human receptionist (₹12–18K/mo) | Business hours only, attrition, no logs | 24×7, 1/4 cost, every interaction logged |
| WhatsApp Business app (free, manual) | Owner is the bottleneck; slow replies lose patients | Instant replies, real bookings, zero owner effort |
| Generic chatbot builders (Wati/Interakt flows) | Rigid menus, no vernacular NLU, owner must build flows | Works out of the box, understands Hinglish/Odia, voice line |
| Practo & marketplaces | They own the patient relationship, charge per lead | Vaani works on the clinic's own number and brand |
| US voice-AI products | English-first, $ pricing, no DPDP posture | Vernacular, ₹ pricing, India-region data, DPDP-native |

**Moat narrative (for content & sales):** compliance-safe by design (Meta 2026 policy + DPDP), vernacular accuracy proven on real calls, outcome-priced. Generic wrappers can't claim any of the three.

## 2. Pricing (locked after Q1 verification)

| Plan | Price | Includes | Overage |
|------|-------|----------|---------|
| **Starter** | ₹2,999/mo | WhatsApp agent, bookings, reminders, dashboard, 1,000 conversations/mo, 1 location, 3 practitioners | ₹2/extra conversation; ₹49/confirmed booking beyond 50/mo |
| **Pro** | ₹6,999/mo | Everything in Starter + voice line (300 min/mo), payment links, weekly ROI report, priority support | ₹4/extra voice minute |
| **Custom (Xolver services)** | ₹25K+ setup + plan | Multi-branch, integrations, custom flows | scoped |

Rules: all prices **+18% GST**, quoted as "₹2,999 + GST" in every asset; GST tax invoice auto-issued monthly (owners' accountants demand it — see PRD F-17). Annual prepay = 2 months free. Pilot = 30 days free with UPI Autopay mandate captured upfront (both plans are under the ₹15,000 no-AFA autopay limit, so renewals debit without per-charge approval — kills conversion friction). No discounting below list in first 25 customers — protect the reference price.

**Pricing risks:** (a) Meta conversation charges shift → margin sensitivity is modeled in TRD §7; re-verify quarterly. (b) ₹2,999 may be under-priced if recovered-booking value averages >₹10K/mo — revisit at 25 customers with willingness-to-pay data; raising later is easier with ROI proof.

## 3. ICP & Beachhead

**ICP v1:** dental + general clinics, 1–3 practitioners, Tier-1/2 city, ≥30 inbound contacts/day, owner-operated, already active on WhatsApp. **Beachhead:** Bhubaneswar (founder proximity = fast feedback loops), then Cuttack, then one metro in Month 5 via remote onboarding.

**Language–city coupling (expansion constraint):** city choice #3 must match the shipped language set. Hyderabad needs Telugu, Pune needs Marathi — both violate the v1 four-language limit (PRD Non-Goal 6). Month-5 options that need **zero new languages**: Kolkata-adjacent Hindi belts, Raipur, Ranchi, Patna, Lucknow/Kanpur, Indore, Jaipur, Delhi NCR. Pick the metro from this list, or budget a full language-pack cycle (templates ×7, eval set ×300 utterances, STT validation) before entering a new linguistic zone. Language packs, not features, are the real expansion unit for an Indian vernacular product.

Disqualifiers (do not sell to): hospitals/chains (procurement cycles), clinics with full-time reception staff who feel threatened (champion risk), owners wanting marketing blasts (policy risk).

## 4. Channels (priority order)

1. **Founder-led direct sales (Months 1–4):** walk-ins/referrals to clinics; demo = live WhatsApp conversation with their own FAQ loaded in <24h ("watch it answer your patients tomorrow"). Demo closer: the missed-call bridge — owner gives their own clinic a missed call from a spare phone and watches Vaani open a WhatsApp booking chat ("miss call do, appointment pao"). Target: 3 demos/week, 40% close to pilot.
2. **Build-in-public (@subhamjena.ai, from Week 3):** weekly artifact from real pilot data — "Clinic X recovered ₹47K of missed bookings in 30 days" carousel; agent-call recordings (consented, anonymized); build logs. Purpose: inbound demos + talent/investor optionality. Fits existing Wired to Win series.
3. **Referral loop (Month 4+):** 1 month free per referred paying clinic, both sides. Clinic owners cluster in WhatsApp groups and associations — one happy dentist is a distribution node.
4. **Dental associations / dealer channel (Month 5+):** local IDA chapter demos; dental-supply salespeople as commissioned referrers (₹1,500/converted clinic).
5. **Product-led loops (Phase 3+):** discreet "Powered by Vaani" footer on patient-facing messages (removable on Pro) pointing to a demo-by-missed-call number — every patient conversation doubles as an ad to other SMB owners in the same WhatsApp ecosystem; referral CTA embedded in the weekly ROI summary owners already screenshot into their clinic-owner WhatsApp groups.
6. **NOT doing in v1:** paid ads (CAC unknowable pre-case-study), marketplaces, cold email at scale.

## 5. Phase-0 Interview Script (validation)

1. Walk me through yesterday: how many calls came in? How many did you or staff miss? (anchor on a real day, not averages)
2. What happens to a missed call today? Do you call back? How often does that patient book elsewhere?
3. What's a new patient worth to you in the first visit? Over a year?
4. Who answers WhatsApp today? How fast? Show me the last 5 chats (ask permission).
5. If a system answered every call and WhatsApp in Hindi/Odia and booked appointments into your calendar, what would worry you about it? (surface objections: trust, wrong info, patient reaction)
6. Price test (sequential): "Would ₹6,000/month be fair for that?" → reaction → "It's ₹2,999." (anchor high, land at list)
7. Close: "I'm taking 5 clinics for a free 30-day pilot this month, then ₹2,999. Should I include you?" → LOI on the spot.

Scoring: a qualified LOI = ≥10 missed contacts/day claimed + owner signed + autopay mandate agreed for post-trial.

## 6. Sales Assets to Produce

- 1-page pilot LOI (Leegality eSign) — Week 1.
- Demo WABA with a fictional clinic KB — Week 3.
- ROI calculator (missed calls × booking value × recovery rate) as WhatsApp-shareable image — Week 4.
- 3 case studies (numbers + owner quote + 30-sec video) — Months 3–4.
- Objection sheet: "Will patients hate a bot?" (data: containment + CSAT from pilots), "What about wrong info?" (KB-grounding + zero-hallucination gate + human handoff), "Is this allowed on WhatsApp?" (compliance one-pager).

## 7. Funnel Targets

| Stage | Month 2 | Month 4 | Month 6 |
|-------|---------|---------|---------|
| Demos | 12 | 30 cum. | 60 cum. |
| Pilots started | 5 | 14 | 30 |
| Paying | 0 (trial) | 10 | 25 |
| Churned | — | ≤1 | ≤2 |

CAC target (founder time excluded): <₹2,000/customer through Month 6. Payback <1 month at Starter pricing.

**PMF instrumentation (don't scale on vibes):** Sean Ellis survey per owner at day 45 — ≥40% "very disappointed if Vaani disappeared" is the green light for city 2; <25% means fix value before scaling sales. Patient CSAT ≥4.3 (F-21) and the cohort retention curve (flat after month 2 = scale signal) reviewed monthly alongside logo counts — 25 logos with a decaying curve is a treadmill, not PMF.

## 8. Brand & Naming Note

"Vaani" is a working codename. Before public launch: trademark search (India, class 9/42), domain + WhatsApp display-name availability, and check for conflicts with existing voice-AI products in India. Decision by end of Phase 1. Product ships under its own brand; "by Xolver" as endorsement line — keeps Xolver's studio positioning clean and lets the product be sold/spun out later.
