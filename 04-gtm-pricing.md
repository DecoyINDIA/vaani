# GTM & Pricing Plan — Project Vaani

**Version:** 3.0 | **Date:** 11 Nov 2026 (v2.0: 18 Jul 2026)

---

## 1. Positioning

**One-liner:** "Your business's AI front office — answers every call and WhatsApp in Hindi, Odia or English, books appointments, follows up with your customers, and tells you each morning how yesterday went."

**Two agents, one bundle:**

| Agent | What the owner sees |
|-------|---------------------|
| **Front-desk agent** | Every call and message answered; appointments booked; reminders, no-show recovery and follow-ups sent; payment links collected. Staff only step in when a person is really needed. |
| **Reporting agent** | A short WhatsApp brief each morning: bookings, revenue recovered, missed contacts, what needs a decision. |

**Time-to-wow:** live on the business's own number, answering real customers, within 24 hours of "yes" — the demo *is* the onboarding (KB auto-draft, F-23). "Watch it answer your customers tomorrow" is a claim competitors doing 2-week flow-builder setups cannot match.

**Against alternatives:**
| Alternative | Their weakness | Our wedge |
|-------------|----------------|-----------|
| Human receptionist (₹12–18K/mo) | Business hours only, attrition, no logs | 24×7, a fraction of the cost, every interaction logged |
| WhatsApp Business app (free, manual) | Owner is the bottleneck; slow replies lose customers | Instant replies, real bookings, zero owner effort |
| Generic chatbot builders (Wati/Interakt flows) | Rigid menus, no vernacular NLU, owner must build flows | Works out of the box, understands Hinglish/Odia, voice line |
| Marketplaces and listing apps | They own the customer relationship, charge per lead | Vaani works on the business's own number and brand |
| US voice-AI products | English-first, $ pricing, no DPDP posture | Vernacular, ₹ pricing, India-region data, DPDP-native |
| CRM / accounting suites (Zoho, Tally) | Records after the fact; nobody answers the phone | Vaani captures the conversation and the booking; integrate with them later |

**Moat narrative (for content & sales):** compliance-safe by design (Meta 2026 policy + DPDP), vernacular accuracy proven on real calls, outcome-priced, and configured per business without custom code. Generic wrappers can't claim any of the four.

## 2. Pricing — under review

The prices below were locked for a WhatsApp-only receptionist (pricing memo, 18 Jul 2026). Per-tenant running cost is fine (65–76% gross margin), but revenue per account is too low to pay for acquisition, onboarding and support. The combined Front-desk + Reporting bundle replaces more of an owner's or employee's time, so it should be priced against that time. **Decide the bundle price from Phase-0 interviews before the first LOI is signed.**

Current baseline:

| Plan | Price | Includes | Overage |
|------|-------|----------|---------|
| **Starter** | ₹2,999/mo | WhatsApp front-desk agent, bookings, reminders, dashboard, 1,000 conversations/mo, 1 location, 3 staff calendars | ₹2/extra conversation; ₹49/confirmed booking beyond 50/mo |
| **Pro** | ₹6,999/mo | Everything in Starter + voice line (300 min/mo), payment links, daily owner brief and ROI report, priority support | ₹4/extra voice minute |
| **Custom (Xolver services)** | ₹25K+ setup + plan | Multi-branch, integrations, custom flows | scoped |

**To test in interviews (not decided):** a single bundle priced against the salary it absorbs, with the outcome overage kept; and whether owners value the daily brief enough to pay for it separately.

Rules: all prices **+18% GST**, quoted as "₹X + GST" in every asset; GST tax invoice auto-issued monthly (PRD F-17). Annual prepay = 2 months free. Pilot = 30 days free with UPI Autopay mandate captured upfront (plans under the ₹15,000 no-AFA autopay limit renew without per-charge approval). No discounting below list in the first 25 customers — protect the reference price.

**Pricing risks:** (a) Meta conversation charges shift → margin sensitivity is modeled in TRD §7; re-verify quarterly. (b) Fixed infra cost spread over few tenants (₹8,400/mo over 25 tenants in the memo) is much heavier at 5 tenants; model margin at actual tenant count, not capacity. (c) Raising price later is easier with ROI proof — revisit at 25 customers with willingness-to-pay data.

## 3. ICP & Beachhead

**ICP v1:** owner-operated, appointment-driven SMBs with 1–10 people, Tier-1/2 city, ≥30 inbound contacts/day, already active on WhatsApp. Examples: clinics, salons and spas, coaching and tuition centres, diagnostic labs, studios, repair and service shops, tailors and boutiques taking appointments, driving schools, interior and photography studios.

**Fit test (use on every prospect):** (1) customers contact them by call or WhatsApp, (2) the business sells time or slots, (3) the owner or a named person owns the schedule, (4) missed contacts are costly. Fail any one and it is not v1.

**Beachhead:** Bhubaneswar (founder proximity = fast feedback loops), across trades. Aim for at least 3 trades with 3+ customers each before treating the product as horizontal (PRD G8). Then Cuttack, then one metro in Month 5 via remote onboarding.

**Language–city coupling (expansion constraint):** the next city must match the shipped language set. Hyderabad needs Telugu, Pune needs Marathi — both violate the v1 four-language limit (PRD Non-Goal 7). Options that need **zero new languages**: Kolkata-adjacent Hindi belts, Raipur, Ranchi, Patna, Lucknow/Kanpur, Indore, Jaipur, Delhi NCR. Language packs, not features, are the real expansion unit for an Indian vernacular product.

**Disqualifiers (do not sell to):** large chains and hospitals (procurement cycles); businesses whose staff feel threatened by the agent (champion risk); owners wanting marketing blasts (policy risk); businesses that mainly need order-taking, quotes or inventory (not a v1 capability).

## 4. Channels (priority order)

1. **Founder-led direct sales (Months 1–4):** walk-ins and referrals across Bhubaneswar's markets and business streets; demo = live WhatsApp conversation with their own FAQ loaded in <24h ("watch it answer your customers tomorrow"). Demo closer: the missed-call bridge — the owner gives their own business a missed call from a spare phone and watches Vaani open a WhatsApp booking chat. Target: 3 demos/week, 40% close to pilot.
2. **Build-in-public (@subhamjena.ai, from Week 3):** weekly artifact from real pilot data — "Salon X recovered ₹47K of missed bookings in 30 days" carousel; agent-call recordings (consented, anonymized); build logs. Purpose: inbound demos + talent/investor optionality. Fits existing Wired to Win series.
3. **Referral loop (Month 4+):** 1 month free per referred paying business, both sides. Owners cluster in WhatsApp groups and trade associations — one happy owner is a distribution node, and referrals across trades prove breadth.
4. **Trade and market associations (Month 5+):** local chambers, market associations and trade bodies for demos; suppliers' salespeople as commissioned referrers (₹1,500 per converted business).
5. **Product-led loops (Phase 3+):** discreet "Powered by Vaani" footer on customer-facing messages (removable on Pro) pointing to a demo-by-missed-call number; referral CTA embedded in the daily brief owners already screenshot into their WhatsApp groups.
6. **NOT doing in v1:** paid ads (CAC unknowable pre-case-study), marketplaces, cold email at scale.

## 5. Phase-0 Interview Script (validation)

Interview at least 20 owners across **4 or more trades**; record the trade so G8 can be measured.

1. Walk me through yesterday: how many calls and messages came in? How many did you or staff miss? (anchor on a real day, not averages)
2. What happens to a missed call today? Do you call back? How often does that customer book elsewhere?
3. What is a new customer worth to you on the first visit? Over a year?
4. Who answers WhatsApp today? How fast? Show me the last 5 chats (ask permission).
5. Who follows up with customers who did not show up or have not been back? How often does it actually happen?
6. How do you know how the day or week went? What do you look at, and how long does it take?
7. If a system answered every call and WhatsApp in Hindi/Odia, booked appointments, followed up, and sent you a morning summary, what would worry you? (surface objections: trust, wrong info, customer reaction)
8. Price test (sequential): anchor on the salary it replaces, then "Would ₹X/month be fair for that?" → reaction → the list price. Record the number the owner volunteers.
9. Close: "I'm taking 5 businesses for a free 30-day pilot this month, then the monthly price. Should I include you?" → LOI on the spot.

Scoring: a qualified LOI = ≥10 missed contacts/day claimed + owner signed + autopay mandate agreed for post-trial.

## 6. Sales Assets to Produce

- 1-page pilot LOI (Leegality eSign) — Week 1.
- Demo WABA with a fictional business KB, one per target trade (clinic, salon, coaching) — Week 3.
- ROI calculator (missed contacts × booking value × recovery rate) as a WhatsApp-shareable image — Week 4.
- 3 case studies from **different trades** (numbers + owner quote + 30-sec video) — Months 3–4.
- Sample daily brief, as a screenshot owners can forward.
- Objection sheet: "Will customers hate a bot?" (data: containment + CSAT from pilots), "What about wrong info?" (KB-grounding + zero-hallucination gate + human handoff), "Is this allowed on WhatsApp?" (compliance one-pager).

## 7. Funnel Targets

| Stage | Month 2 | Month 4 | Month 6 |
|-------|---------|---------|---------|
| Demos | 12 | 30 cum. | 60 cum. |
| Pilots started | 5 | 14 | 30 |
| Paying | 0 (trial) | 10 | 25 |
| Churned | — | ≤1 | ≤2 |
| Trades with ≥3 paying | — | 1 | 3 |

CAC target (founder time excluded): <₹2,000/customer through Month 6. Payback target is under one month **at the price decided in §2**; recompute once the bundle price is set.

**PMF instrumentation (don't scale on vibes):** Sean Ellis survey per owner at day 45 — ≥40% "very disappointed if Vaani disappeared" is the green light for city 2; <25% means fix value before scaling sales. Customer CSAT ≥4.3 (F-21) and the cohort retention curve (flat after month 2 = scale signal) reviewed monthly alongside logo counts — and **cut by trade**, so one strong trade cannot hide a weak one.

## 8. Brand & Naming Note

"Vaani" is a working codename. Before public launch: trademark search (India, class 9/42), domain + WhatsApp display-name availability, and check for conflicts with existing voice-AI products in India. Decision by end of Phase 1. Product ships under its own brand; "by Xolver" as endorsement line — keeps Xolver's studio positioning clean and lets the product be sold/spun out later.
