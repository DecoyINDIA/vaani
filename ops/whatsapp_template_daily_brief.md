# WHATSAPP TEMPLATE — DAILY BRIEF (DRAFT, NOT YET SUBMITTED)

Kept apart from `whatsapp_templates.md`, which is the pinned approval artifact for the 8-template pack already prepared for Meta (a test fixes its section count). Submit this one separately once the wording has been reviewed.

## T_DAILY_BRIEF (Daily Brief to Owner) — DRAFT, not yet submitted to Meta
*   **Registry name:** `daily_brief_owner`. Requested category: utility; Meta approval and the approved category remain pending. The scheduler checks every 15 minutes and attempts delivery during the tenant's 08:00 hour for the previous local calendar day. No catch-up runs after that hour.
*   **Variables:** `{{1}}` = Business Name, `{{2}}` = Date (e.g. "Mon, 09 Nov"), `{{3}}` = Conversations, `{{4}}` = Confirmed Bookings, `{{5}}` = Recovered Bookings (after-hours/voice), `{{6}}` = Estimated Recovered Value, `{{7}}` = Open Escalations
*   **Review needed:** Hindi, Hinglish and Odia wording below is a first draft and needs a native-speaker read before submission.
*   **Current worker language:** English (`en`). The worker does not yet select a tenant language; the other variants below are editorial drafts, not evidence of provider-supported or approved locale codes.
*   **Components:** Body only, seven positional text parameters. No header, footer or dashboard button is included in this submission draft. A dashboard button needs a separately specified URL and approval before adding it.

### Runtime contract and synthetic submission samples

| Position | Runtime key | Meaning | Sample |
| --- | --- | --- | --- |
| `{{1}}` | `owner_name` | Tenant business name, despite the legacy key name | Glow Salon |
| `{{2}}` | `date_str` | Previous local day, formatted by the worker | Mon, 09 Nov |
| `{{3}}` | `convs_count` | Conversations started during that day | 12 |
| `{{4}}` | `confirmed_count` | Bookings created that day whose current status is confirmed or completed | 5 |
| `{{5}}` | `recovered_count` | Those bookings created by voice or outside configured business hours; counted once | 2 |
| `{{6}}` | `revenue_str` | Recovered count × configured average booking value in INR; estimate, not collected revenue | Rs. 3000 |
| `{{7}}` | `open_escalations` | All currently open escalations at send time, including earlier days | 1 |

The reporting window includes yesterday's local midnight and excludes today's local midnight, converted to UTC. Recovery uses `business_hours`; missing/empty hours fall back to 09:00–18:00 Monday–Saturday, closed Sunday. Missing or invalid `business_profile.avg_booking_value` falls back to Rs. 1000.

This report does not count missed calls or a separate “needs your decision” category. “Conversations” counts conversation records, not individual calls or messages.

### English (en)
> Good morning {{1}}! Yesterday ({{2}}) with Vaani:
> 💬 Conversations Started: {{3}}
> 📅 Confirmed / Completed Bookings Created: {{4}}
> 🔄 Recovered Bookings: {{5}} (after-hours/voice)
> 💰 Est. Recovered Booking Value: {{6}}
> ⏳ Waiting for your team: {{7}}

### Hindi (hi)
> सुप्रभात {{1}}! कल ({{2}}) वाणी के साथ:
> 💬 संभाली गई बातचीत: {{3}}
> 📅 बुक किए गए अपॉइंटमेंट: {{4}}
> 🔄 वापस पाए गए अपॉइंटमेंट: {{5}} (बंद समय/कॉल)
> 💰 अनुमानित बची हुई कमाई: {{6}}
> ⏳ आपकी टीम का इंतज़ार: {{7}}

### Hinglish (hi-Latn)
> Good morning {{1}}! Kal ({{2}}) Vaani ke saath:
> 💬 Handled Calls & Chats: {{3}}
> 📅 Booked Appointments: {{4}}
> 🔄 Recovered Bookings: {{5}} (after-hours/voice)
> 💰 Est. Recovered Revenue: {{6}}
> ⏳ Aapki team ka wait: {{7}}

### Odia (or)
> ସୁପ୍ରଭାତ {{1}}! ଗତକାଲି ({{2}}) ବାଣୀ ସହିତ:
> 💬 ସମାଧାନ ହୋଇଥିବା କଲ୍ ଓ ଚାଟ୍: {{3}}
> 📅 ବୁକ୍ ହୋଇଥିବା ଅପଏଣ୍ଟମେଣ୍ଟ: {{4}}
> 🔄 ଉଦ୍ଧାର ହୋଇଥିବା ବୁକିଂ: {{5}} (ବନ୍ଦ ସମୟ / କଲ୍)
> 💰 ଆନୁମାନିକ ଉଦ୍ଧାର ହୋଇଥିବା ରାଜସ୍ୱ: {{6}}
> ⏳ ଆପଣଙ୍କ ଟିମ୍‌ର ଅପେକ୍ଷାରେ: {{7}}

### Acceptance still pending

- Native-speaker review of the Hindi, Hinglish and Odia drafts against the metric definitions above; they have not been certified as equivalent to the English body.
- Operator submission and recorded Meta approval of the exact name, body, seven parameter positions and selected language. Presence in `TEMPLATE_PACK` is a local allowlist entry, not proof of approval; there is no approval-status gate in the worker. Keep `daily_brief_enabled: false` for real tenants awaiting approval.
- An authorized sandbox send outside an open conversation window, with provider message ID and delivery-status evidence. Offline tests cannot establish provider acceptance or delivery.
- An intentional rollout decision after approval and sandbox validation. No live send or submission is recorded here.

Implementation references: `app/workers/daily_brief.py`, `app/reporting.py`, `app/channels/whatsapp.py`. Offline regressions: `tests/test_daily_brief.py`; weekly compatibility: `tests/test_phase3.py` and `tests/test_outbound_delivery.py`.

