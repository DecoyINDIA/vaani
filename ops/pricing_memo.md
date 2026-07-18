# PRICING MEMO — RESOLVING Q1 & STARTER PLAN MARGIN LOCK
**Project Vaani — Validation Phase**

**Date:** July 18, 2026  
**Author:** Subham Jena, Founder  
**Status:** Locked for Phase 0 G0 Gate  

---

## 1. Context & Purpose (Q1 Resolution)
In the previous conversation-based pricing model of the WhatsApp Business Platform, every 24-hour interaction window was billed as a conversation, costing between ₹0.30 and ₹0.50 in India depending on the category. In July 2025, Meta transitioned to a **per-message billing model** where:
1.  **Service messages (replies to patient-initiated incoming queries) inside the 24-hour window are completely free.**
2.  **Utility templates (order confirmation, reminder, payment link) are billed per delivered message** only when sent. The current India list rate is **₹0.135 per utility message**.
3.  **BSP (Business Solution Provider) markups and platform fees** are added on top of the Meta fees.

This pricing memo resolves **PRD Q1** by verifying our actual margin structure on the **Starter Plan (₹2,999/mo + 18% GST)** and establishing strict volume controls to lock in a **minimum gross margin of 60%**.

---

## 2. Meta & BSP Cost Structure (India, July 2026)

We will routing our messages through a standard verified BSP (e.g., Aisensy/Wati/Interakt or direct Meta Cloud API with a BSP management fee). The billing rates are structured as follows:

*   **Meta Utility Template Base Rate:** ₹0.135 / message
*   **BSP Transactional Markup:** ₹0.045 / message
*   **Effective Cost per Utility Message:** **₹0.18**
*   **BSP Flat Platform Fee (Amortized per tenant):** **₹200 / month**
*   **Service Messages (Inbound replies):** **₹0.00**

---

## 3. Traffic Modeling (Starter Plan: 1,000 Conversations/mo)

We model a "standard clinic tenant" on the Starter Plan.
*   **Base Subscription:** ₹2,999/mo (excluding GST).
*   **Total Monthly Conversations:** 1,000.
*   **Estimated Appointment Conversions:** 350 bookings/month (based on 50% booking conversion target F-03 of qualified leads).

### A. Meta Out-of-Window Utility Charges
1.  **T-24h Reminders:** 350 bookings × 1 reminder = 350 messages. All sent outside the 24-hour window, so 100% are billed as utility.
    *   *Cost:* 350 × ₹0.18 = ₹63.00
2.  **T-2h Reminders:** 350 bookings × 1 reminder = 350 messages.
    *   *Assumption:* 60% of patients reply to the 24h reminder (e.g., clicking "✅ आऊँगा" or asking a question), which opens a new 24h service window. Thus, 60% of the 2h reminders are sent inside the open window (free). The remaining 40% are sent to unresponsive patients and are billed.
    *   *Cost:* 350 × 40% × ₹0.18 = 140 × ₹0.18 = ₹25.20
3.  **Missed-Call Bridge & Proactive Messages:** 250 conversations/mo are initiated by Vaani (e.g., missed-call template or proactive confirmation sent from dashboard/voice). Billed as utility.
    *   *Cost:* 250 × ₹0.18 = ₹45.00
4.  **In-chat CSAT Request (F-21):** Sent within the 24h window at conversation resolution.
    *   *Cost:* 0 (Free Service Message)

**Total Meta/BSP Transactional Costs:** ₹63.00 + ₹25.20 + ₹45.00 = **₹133.20 / month**

---

## 4. Other Operating COGS (Per Tenant/mo)

### A. LLM Token Costs (OpenRouter Hybrid Model)
We assume an average of 4 turns (inbound + outbound) per conversation. 1,000 conversations = 4,000 turns.
*   **Classifier Node (Gemini 1.5 Flash):** ~250 input tokens, ~15 output tokens per turn.
    *   *OpenRouter rate:* Input $0.075/M tokens, Output $0.30/M tokens.
    *   *Cost per turn:* (250 × $0.000000075) + (15 × $0.0000003) = $0.00002325 ≈ ₹0.002
*   **Responder Node (GPT-4o-mini):** ~1,500 input tokens (including KB snippets), ~120 output tokens per turn.
    *   *OpenRouter rate:* Input $0.15/M tokens, Output $0.60/M tokens.
    *   *Cost per turn:* (1500 × $0.00000015) + (120 × $0.0000006) = $0.000297 ≈ ₹0.025
*   **Total LLM Cost per Turn:** ₹0.027
*   **Total LLM Cost/mo (4,000 turns):** 4,000 × ₹0.027 = **₹108.00 / month**

### B. Shared Infrastructure Costs
We run our core web app, Redis, and Caddy on a single virtual private server (VPS) in the Mumbai region, with MongoDB Atlas.
*   **Shared Costs:** M10 Atlas cluster ($80/mo) + VPS ($20/mo) = $100/mo ≈ ₹8,400/mo.
*   **Amortization (at 25 tenants capacity):** ₹8,400 / 25 = **₹336.00 / month**

---

## 5. Gross Margin Analysis (Starter Plan)

We present three scenarios based on traffic volatility and model choices.

| Cost Line | Scenario 1: Optimistic (800 conv/mo, Flash responder) | Scenario 2: Base Case (1,000 conv/mo, 4,000 turns) | Scenario 3: Pessimistic (1,500 conv/mo, heavy LLM) |
| :--- | :--- | :--- | :--- |
| **Meta/BSP Charges** | ₹100.00 | ₹133.20 | ₹220.00 |
| **BSP Platform Fee** | ₹200.00 | ₹200.00 | ₹200.00 |
| **LLM Costs** | ₹65.00 | ₹108.00 | ₹280.00 |
| **Infra Amortized** | ₹336.00 | ₹336.00 | ₹336.00 |
| **Total COGS** | **₹701.00** | **₹777.20** | **₹1,036.00** |
| **Revenue (Starter)** | ₹2,999.00 | ₹2,999.00 | ₹2,999.00 |
| **Gross Margin %** | **76.62%** | **74.08%** | **65.45%** |

---

## 6. Verification Verdict & Margin Lock Controls

> [!TIP]
> The per-message pricing regime introduced by Meta significantly improves the unit economics of Project Vaani compared to conversation-based pricing. Because user-initiated conversations cost ₹0 in Meta charges for the actual dialogue, our gross margin comfortably sits between **65% and 76%**, passing the G0 exit gate of **>60% margin**.

To guarantee that margins stay locked above 60% as we scale, the engineering team will enforce the following boundaries in Phase 1 billing code:
1.  **Hard Caps in Starter Plan:** Cap conversations at 1,000/month. Any conversation beyond this is billed at ₹2 overage per conversation.
2.  **Overage for Bookings:** Confirmed bookings are capped at 50/month. Confirmed bookings beyond 50/mo are billed at ₹49/booking (this maps directly to the value of recovered patient slots).
3.  **Pro Plan telecommunication lock:** Voice pricing (Pro Plan ₹6,999/mo) includes 300 minutes. We lock an overage fee of **₹4/minute** for additional call duration. Voice COGS must not exceed ₹4/min during the Phase 2 bake-off.
