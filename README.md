<p align="center">
  <img src="assets/hero.svg" alt="Vaani: Your business, always answered. AI front desk that books appointments on WhatsApp and voice" width="800">
</p>

<h1 align="center">Vaani — Your business, always answered.</h1>

<p align="center"><em>Every call answered. Every booking secured. In the language your customers speak.</em></p>

<p align="center">
  <strong>WhatsApp & Voice Front Office for Indian Small and Medium Businesses</strong><br>
  Clinics · Salons · Coaching Centres · Studios · Service Garages
</p>

---

## The Emotional Promise

Your customers are heard. Your appointments are handled. **You remain in control.**

Vaani is an AI-powered front office employee built for everyday Indian small and medium businesses. It answers customer calls and WhatsApp messages in **Hindi, Odia, Hinglish, and English**, books appointments with atomic conflict prevention, sends automatic reminders, and provides the business owner with a **morning brief** summarizing yesterday’s revenue and bookings.

Vaani always discloses that it is an AI assistant. It never pretends to be human, and it never guesses a fact — answering strictly from approved business records with verified human escalation.

---

## Two Agents, One Cohesive System

```
  ┌────────────────────────────────────────────────────────┐
  │                 CUSTOMER INTERACTION                   │
  │     WhatsApp Messages  ·  Inbound & Missed Calls       │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                   FRONT-DESK AGENT                     │
  │  • Answers in Hindi, Odia, Hinglish & English          │
  │  • 2-Tap Booking via List Messages & Reply Buttons    │
  │  • Missed-Call-to-WhatsApp Bridge (F-16)               │
  │  • Reminders, Rescheduling & Waitlist Auto-Backfill    │
  │  • UPI Payment Links (Razorpay)                        │
  │  • 1-Tap Human Takeover & Seamless Return              │
  └──────────────────────────┬─────────────────────────────┘
                             │
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                   REPORTING AGENT                      │
  │  • Daily WhatsApp Brief at 08:00 AM (F-13)             │
  │  • Recovered Bookings & After-Hours Revenue Ticker     │
  │  • Escalations Needing Owner Decision                  │
  └────────────────────────────────────────────────────────┘
```

---

## What Makes Vaani Different

1. **Taps Over Typing (2-Tap Booking):** No endless conversational back-and-forth. Slot selection is presented as native WhatsApp list messages and reply buttons.
2. **The Missed-Call-to-WhatsApp Bridge:** When the business phone line is busy or engaged, Vaani immediately opens a WhatsApp conversation offering open slots within 30 seconds.
3. **Zero Hallucination Guarantee:** Dual-scope compliance gates and discrete token verification block fabricated pricing, unauthorized discounts, or incorrect business hours. If an answer isn't in approved knowledge, Vaani offers an appointment or routes to staff.
4. **Cultural & Language Fluency:** Natively understands colloquial Hindi, Odia, Hinglish, and English with relative date understanding (*"kal/parso"*) and landmark-based directions.
5. **Radical Owner Control:** A modern, distraction-free control desk providing a real-time schedule, 1-tap customer takeover, and knowledge verification sandbox.
6. **Built for India’s DPDP Act:** Strict tenant isolation, privacy notice consent recording, and statutory data retention compliance.

---

## The Owner Workspace

The redesigned **Vaani Business Desk** gives owners a calm, unified command center:

- **Today:** Yesterday’s WhatsApp Morning Brief preview, real-time pulse stats, and urgent handoff queue.
- **Conversations:** Live WhatsApp inbox with language tags, sentiment indicators, and 1-tap staff takeover.
- **Appointments:** Visual schedule cards with 120s atomic hold verification and waitlist backfill monitoring.
- **Vaani’s Brain:** Approved business knowledge base, landmark instructions, and an interactive **"Test Vaani" sandbox** to test answers before customer traffic arrives.
- **Performance:** End-to-end confirmed bookings counter, recovered after-hours revenue tracker, and 1-tap CSAT metrics.

---

## Architecture & Technology Stack

- **Backend:** FastAPI (Python 3.12+), LangGraph/StateGraph agent core, MongoDB replica set (atomic transactions), Redis durable queue.
- **Telephony & Speech:** Exotel AgentStream WebSockets, Sarvam Saaras v4 STT & Bulbul v3 TTS.
- **Messaging:** Meta WhatsApp Cloud API (Utility & Service templates).
- **Frontend Desk:** React 18, Vite, TypeScript, Tailwind CSS, Warm Intelligence design tokens.
- **Quality Gates:** 191 offline CI tests, 500-concurrent-claim race test validation, Trivy container security scans.

---

## Getting Started

### Prerequisites
- Node.js 22+ & npm
- Python 3.12+ & `uv`
- MongoDB & Redis (or Docker Compose)

```bash
# 1. Clone the repository
git clone https://github.com/DecoyINDIA/vaani.git
cd vaani

# 2. Install backend dependencies
uv sync

# 3. Build the owner dashboard
npm --prefix dashboard install
npm --prefix dashboard run build

# 4. Run tests
uv run pytest -q

# 5. Start development server
uv run uvicorn app.main:app --reload --port 8000
```

---

## License & Attribution

Proprietary. Developed by **Subham Jena, Xolver**. All rights reserved.  
In active development for pilot deployments in Bhubaneswar and Tier-1/2 Indian hubs.
