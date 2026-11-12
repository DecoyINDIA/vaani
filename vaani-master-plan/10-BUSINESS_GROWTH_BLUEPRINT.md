# 10 — BUSINESS GROWTH BLUEPRINT

Labels: **[REPO]** stated in the repository's planning docs · **[EXT]** external web source, vendor-published and not independently verified · **[HYP]** my hypothesis · **[CALC]** arithmetic on stated assumptions. No figure here is a forecast.

## 1. Where the business actually stands

- A product that has never served a patient, a pricing page, and a go-to-market plan. **[REPO]**
- The plan's own Gate G0 — five signed pilot LOIs before any code — has no evidence of completion in the repository. **[REPO/UNKNOWN]**
- The largest risk is therefore commercial, not technical: nobody has yet shown that a clinic owner will pay or that patients will finish a booking with the bot.

**Implication:** every commercial decision below is framed as an experiment with a pass/fail line, to be run with the first 3–5 clinics.

## 2. Customer and pain

**Target [REPO]:** dental and general clinics, 1–3 practitioners, owner-operated, Tier-1/2 city, ≥ 30 inbound contacts a day, already on WhatsApp. Beachhead Bhubaneswar.

**Pain [REPO, plausible]:** missed calls and slow WhatsApp replies lose patients; a receptionist costs ₹12–18K a month and covers business hours only.

**Unvalidated assumptions to test in the first interviews [HYP]:**
1. Clinics book by **fixed time slots**. Many small Indian clinics run token/walk-in queues; if so the booking engine fits poorly and "reserve a token for the morning session" is the real product.
2. The **owner** will operate a web dashboard. Often it is a receptionist on a phone, or nobody.
3. Patients will **tap through** a list picker rather than insist on a call.
4. The buyer values **recovered bookings** more than **staff time saved**. This decides the pitch and the weekly report.

## 3. Competitive landscape

| Substitute | Typical price | Position vs Vaani |
|---|---|---|
| Human receptionist | ₹12–18K/mo **[REPO]** | the real incumbent; Vaani complements rather than replaces |
| WhatsApp Business app, manual | free | owner is the bottleneck |
| Flow-builder platforms (AiSensy, Wati, Interakt) | AiSensy AI-agent library ₹3,500/mo **[EXT]** | general-purpose, owner must configure; strong distribution |
| Clinic-specific AI receptionists | CareVoice ₹4,999 / ₹9,999; CatchAI ₹4,999 / ₹11,999; Curastax "from ₹999" **[EXT]** | direct competitors; several look early-stage (demo-grade domains) |
| Managed voice-agent platforms | Sarvam from ~₹3/min incl. telephony; Ringg ₹6/min **[EXT]** | a component Vaani can buy |
| Practo-style marketplaces | per-lead / commission | own the patient relationship |

**Reading [HYP]:** the category exists and is crowded at the low end. ₹2,999 is at or below the market. "AI on WhatsApp" does not differentiate; **proof** does — a named clinic, a measured number of bot-completed bookings, zero wrong answers.

**Platform risk [EXT]:** Meta barred general-purpose AI assistants from the WhatsApp Business API from 15 Jan 2026 while allowing business-specific bots (support, bookings). Vaani's closed-intent, code-enforced scope is squarely on the permitted side and is worth stating in sales material — but Meta keeps discretion, so keep the scope gate strict.

## 4. Positioning (recommended)

> **"Every patient message answered in a minute, in their language — and you see exactly how many appointments it booked."**

Three proof points, each already backed by code once Wave 1–2 land: (1) answers only from facts the clinic approved; (2) books in two taps, hands over to staff when unsure; (3) a weekly count the owner can audit. Drop "voice" from the headline until it is real.

## 5. Unit economics — assumptions and sensitivities

**Base case from the repo's pricing memo [REPO]** (Starter, 1,000 conversations/month):

| Line | ₹/tenant/month | Assumption |
|---|---|---|
| Meta utility templates | 133 | 350 reminders ×2 partly in-window + 250 proactive, at ₹0.18 effective |
| BSP platform fee | 200 | amortized |
| LLM | 108 | 4,000 turns at ₹0.027 |
| Shared infra | 336 | ₹8,400/mo across 25 tenants |
| **COGS** | **≈ 777** | |
| **Gross margin on ₹2,999** | **≈ 74%** **[CALC]** | |

**Sensitivities [CALC]:**

| Scenario | Effect |
|---|---|
| Only 5 tenants share infra (₹1,680 each) | COGS ≈ ₹2,121 → margin ≈ 29%. Margin is a scale outcome, not a property of the plan. |
| LLM cost 3× (larger model or 2 calls/turn at higher token counts) | +₹216 → margin ≈ 67% at 25 tenants |
| **Meta charges for service messages beyond a free tier** | Vendor notices **[EXT]** say that from 1 Oct 2026 service messages are free for the first 1,000 per number per month and in-window utility templates are billable. At 1,000 conversations × ~4 bot messages ≈ 4,000 messages, ~3,000 could be billable. I could not confirm the India service rate; at an **illustrative** ₹0.10–0.35 per message that is +₹300–1,050/tenant/month → margin 39–64% at 25 tenants. |
| Voice at a managed-platform price of ₹3.15–3.50/min **[EXT]** vs ₹4/min overage **[REPO]** | 12–21% gross margin on overage minutes; the 300 included Pro minutes cost ≈ ₹950–1,050 |

**Action H-01:** read Meta's current India rate card and free-tier rules directly (not a BSP blog) and rerun this table. If the service-message change is real, reducing bot messages per conversation (tap flows already help) and pricing conversations become first-order concerns.

**Break-even [CALC]:** contribution per Starter tenant ≈ ₹2,999 − (133 + 200 + 108) ≈ ₹2,560. Against the repo's ₹40–60K/month all-in burn, break-even is ≈ 16–24 paying Starter clinics — consistent with the repo's own 15–20 estimate.

## 6. Pricing and packaging

**Problem [REPO, verified in `app/billing/plans.py`]:** Starter includes 50 bookings, then ₹49 each. The memo's "standard clinic" makes 350 bookings a month → ₹2,999 + 300 × ₹49 = **₹17,699** before GST. That contradicts the ₹2,999 headline and exceeds the ₹15,000 UPI-Autopay limit the plan depends on for frictionless renewal.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| A. Flat ₹2,999, bookings uncapped, 1,000-conversation fair use | simple; matches the pitch; no bill shock | leaves outcome upside on the table |
| B. Keep the overage but raise the included bookings to ~300 | preserves outcome pricing | still complex to explain |
| C. Two tiers by clinic size: Solo ₹2,999 (1 doctor) / Clinic ₹4,999 (up to 3 doctors, staff logins) | prices on a value metric owners understand; in line with ₹4,999 competitors **[EXT]** | needs multi-practitioner (W3-03) to be real |

**Recommendation [HYP]:** pilot on **A**; meter bookings silently; move to **C** once multi-practitioner ships and three clinics have a month of data. Voice becomes a **metered add-on** priced to at least break even, not the Pro anchor. Annual prepay and the UPI-Autopay mechanics from the repo's plan stay.

## 7. Acquisition

Keep the repo's sequence — founder-led direct sales in one city, then referral, then association/dealer channels — with three adjustments:

1. **Sell the pilot, not the product.** Offer: "14 days on your own number, we set it up, you get a daily list of what it handled." Ask for the UPI mandate at the end of the pilot, not the start, for the first three clinics; restore the upfront mandate once there is a case study.
2. **The demo is their own WhatsApp.** Load their fees, timings and doctors before the meeting; let them message it from their own phone. This needs onboarding to take under an hour of operator time (W4-04).
3. **One artifact per pilot:** a single screenshot-able card — "Dr X's clinic, 14 days: N messages answered, M appointments booked without staff, 0 wrong answers." Clinic owners share these in their own groups; it is the cheapest channel available.

Not yet: paid ads, multi-city expansion, a "Powered by Vaani" footer (needs explicit clinic consent and adds a link to every patient message).

## 8. Retention and expansion

- **Retention driver [HYP]:** the owner sees a truthful number every week and staff find the inbox easier than the phone. The current weekly summary invents revenue (₹1,000 × count) — replace it with counts, plus revenue only when the clinic has supplied its own average booking value (W4-02).
- **Early-churn signals to watch:** staff never log in; takeover rate above 50%; owner mutes the summary.
- **Expansion paths, in order of evidence needed:** more doctors/locations (tier C) → payment links for deposits → voice add-on → adjacent verticals (salons, diagnostics, physiotherapy) that share the appointment model and need only KB/template wording — which is why de-hardcoding "dental" (W1-02) is also a market-size decision.

## 9. Validation experiments

| # | Hypothesis | Experiment | Pass line | Cost |
|---|---|---|---|---|
| E1 | Owners will commit | Ask 10 interviewed clinics for a signed pilot LOI | ≥ 3 sign | founder time |
| E2 | Patients complete tap booking | Pilot clinic 1, 14 days | booking conversion ≥ 50% of book intents | Wave 1–3 |
| E3 | The bot is trusted | Daily transcript review | 0 wrong facts; takeover ≤ 40% | founder time |
| E4 | Slots fit the clinic | Interview question + pilot observation | ≥ 3 of 5 clinics use timed appointments | none |
| E5 | Price holds | At day 14 ask for the mandate at ₹2,999 + GST | ≥ 2 of 3 pilots convert | none |
| E6 | Staff will use the dashboard | Count logins and staff replies | ≥ 3 staff sessions/week per clinic | W1-11/12, W3-01 |
| E7 | Voice is wanted enough to pay for | Offer a ₹/min add-on to pilot clinics | ≥ 2 say yes at a break-even price | none until yes |
| E8 | Meta cost model holds | Read the rate card; compare the first real invoice | COGS within 20% of §5 | none |

**Kill/pivot rules (from the repo, kept):** fewer than 3 LOIs from 10 serious conversations → change vertical or price before more engineering. Conversion < 40% after fixes → diagnose quality vs value. Voice COGS above selling price → WhatsApp-only.

## 10. Cost reduction opportunities

1. **One LLM call per booking turn** instead of two (W2-03) — roughly halves LLM spend and latency on the commonest path.
2. **Tap flows cut message count**, which matters if service messages become billable.
3. **Do not run voice infrastructure** until a customer pays for it.
4. **Atlas tier:** the memo assumes M10; start on the smallest tier that supports transactions and Search, move up on evidence.
5. **Agent-built engineering:** route Small packets to inexpensive models; reserve expensive reasoning for the three Advanced tasks and for writing the next wave's packets.

## Sources

External figures above come from these pages; all are vendor or press pages and should be re-checked before being relied on.

- [AiSensy — WhatsApp pricing update, October 2026](https://m.aisensy.com/blog/whatsapp-pricing-update-october-2026/)
- [WATI — Introducing message-based pricing](https://support.wati.io/articles/introducing-message-based-pricing-0MqqSan4Cx)
- [Meta — Pricing on the WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [respond.io — WhatsApp general-purpose chatbots ban](https://respond.io/blog/whatsapp-general-purpose-chatbots-ban)
- [Business Standard — Meta bans AI chatbots from WhatsApp Business API](https://www.business-standard.com/technology/tech-news/meta-bans-ai-chatbots-from-whatsapp-business-api-chatgpt-to-shut-down-jan-2026-125102200335_1.html)
- [Sarvam — Voice agents pricing](https://docs.sarvam.ai/voice-agents/pricing.md)
- [Ringg — AI voice agent pricing](https://www.ringg.ai/ai-voice-agent-pricing)
- [AiSensy — WhatsApp AI agent library (patient queries)](https://aisensy.com/whatsapp-ai-agent-library/patient-queries)
- [CatchAI on GetApp](https://www.getapp.com/all-software/a/catchai/)
- [CareVoice](https://carevoice.duckdns.org/)
- [Curastax](https://curastax.pages.dev/)
