# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Project Vaani — a vernacular AI front-desk agent (WhatsApp + voice) for Indian appointment-driven SMBs; v1 vertical is clinics.

**Current status: pre-code (Phase 0, validation).** The repo contains a planning pack plus project scaffolding (`pyproject.toml`, `.env.example`). No product code ships before gate G0 is met (≥5 signed pilot LOIs — see `03-build-plan.md`). When product code does land, it must follow the layout and rules below, which are specified in detail in `06-engineering-plan.md` and `02-TRD.md`.

### Document map

| Doc | Contents |
|-----|----------|
| `00-overview.md` | Index, key decisions already made, Week-1 blockers, top risks |
| `01-PRD.md` | Problem, personas, P0/P1/P2 requirements, acceptance criteria |
| `02-TRD.md` | Architecture, 7 ADRs, data model, agent design, NFRs, cost model |
| `03-build-plan.md` | Phases 0–3, binary entry/exit gates, kill criteria, budget |
| `04-gtm-pricing.md` | Positioning, pricing, ICP, channels, funnel |
| `05-risk-compliance.md` | Risk register, Meta/WhatsApp policy, DPDP, legal |
| `06-engineering-plan.md` | Repo layout, week-by-week build order, CI/eval gates |

When editing planning docs, keep them consistent with each other — decisions are cross-referenced (e.g., ADR numbers from the TRD, feature IDs like F-16/F-17 from the PRD, gates G0–G2 from the build plan).

## Commands

Python 3.12, uv-managed. Tooling is configured in `pyproject.toml`; the `app/`, `evals/`, `ops/`, `tests/`, `dashboard/` directories do not exist yet.

```bash
uv sync --extra dev            # install runtime + dev dependencies
uv run ruff check .            # lint (rules: E, F, I, UP, B; line length 100)
uv run mypy .                  # typecheck (strict mode, pydantic plugin)
uv run pytest                  # tests (asyncio_mode=auto, testpaths=tests)
uv run pytest tests/test_x.py::test_name   # single test
python evals/run_evals.py      # eval suite: intent F1, scope-gate accuracy, hallucination check
```

CI pipeline (planned, `.github/workflows/ci.yml`): ruff → mypy → unit tests → tenant-isolation suite → eval gate → image build. Nightly: 500-concurrent booking race test + full eval on all 4 languages. Any prompt/template/intent-taxonomy change fails CI unless the eval suite passes (intent F1 ≥ threshold, hallucination incidents = 0).

Environment: copy `.env.example` → `.env` and fill in per its comments (grouped by TRD ADR). All env vars are read through `app/config.py` (pydantic-settings) — never read env directly elsewhere.

## Architecture

Single monorepo, single deployable unit (do not split before 100 tenants; no k8s, no microservices, no separate vector DB).

**Message flow:** Channel webhooks (Meta WhatsApp via BSP; Exotel voice in Phase 2) → FastAPI gateway (signature verification, tenant resolution by phone number, idempotency, <5s ack) → Redis Streams queue → LangGraph worker pool (agent core) → MongoDB Atlas (ap-south-1) + Redis (locks, session cache). Owner dashboard is a Vite + React + shadcn SPA served as static files behind the same FastAPI app.

**Agent core** is a LangGraph state machine with 7 nodes: `lang_detect → intent_classifier → scope_gate → tool_router → responder → output_scope_check → handoff_manager`. It is channel-agnostic — voice is a new channel adapter producing the same normalized events, never a second agent.

**Compliance is enforced in code, not prompts:**
- Closed intent taxonomy (18 intents, TRD §4.1). `medical_question` and `out_of_scope` route to static templates — the LLM responder node is unreachable for them *by graph topology*.
- Dual scope gates: input gate (small classifier model, temperature 0, confidence threshold; two low-confidence turns → human handoff) and output gate (every factual claim — fee/time/service/address — must cite a KB entry or tool result; fail → regenerate once → fallback template).
- Every side-effect is a tool call (`kb_search`, `slots_get`, `booking_create/move/cancel`, `payment_link_create`, `escalate`); every tool call is audited.

**LLM access** is via OpenRouter with models pinned per node (cheap model for classification, frontier model for responses, second-provider failover). Prompts and evals must stay model-portable — no provider-specific features in core paths.

**Booking engine:** slots use optimistic locking — `findOneAndUpdate(status:"open" → "held")` with a 120s hold expiry, then confirm; race-safe by construction. Slot generation respects a per-tenant holiday calendar. The booking tool rejects any call without `date_confirmed=true` (see language rules below).

### Planned repo layout (from `06-engineering-plan.md` §0)

```
app/
├── main.py            # FastAPI app factory
├── config.py          # pydantic-settings; ALL env in one place
├── gateway/           # webhooks: meta.py, razorpay.py, exotel.py + middleware
├── agent/             # graph.py, nodes/, tools/, prompts/, templates/
├── booking/           # slot engine, holiday calendar, relative-date resolver
├── kb/                # KB CRUD, embeddings, Atlas Search hybrid retrieval
├── channels/          # whatsapp.py (send + 24h-window tracker), voice/ (P2)
├── billing/           # usage meters, cost rollup, GST invoices
├── owner_api/         # dashboard REST, JWT auth
├── models/            # pydantic + mongo accessors (tenant_id required)
├── audit.py           # append-only writer; single choke point
└── workers/           # Redis Streams consumers
dashboard/             # Vite + React + shadcn SPA
evals/                 # dataset/, run_evals.py, voice_corpus/
ops/                   # seed_tenant.py, restore_runbook.md, dpdp_delete.py
tests/                 # unit + integration; booking race test
```

## Non-negotiable code rules (enforced in review + CI)

1. **`tenant_id` is an explicit required parameter on every DB accessor** — no default, no ambient tenant context. Raw `db[collection].find` outside `app/models/` is forbidden (CI greps for it). Every collection is compound-indexed on `(tenant_id, …)`.
2. **Every outbound message and tool call goes through `audit.py`** — no direct sends.
3. **No LLM call outside `agent/nodes/` and `agent/tools/kb_search`.**
4. **Prompt/template/taxonomy changes require the eval suite to pass** (intent F1 ≥ threshold, hallucination = 0) before merge.
5. **Anything user-facing exists in all 4 languages (hi, en, hi-Latn "Hinglish", or) or doesn't ship.**

## Language & India-market rules

- Templates and copy default to respectful register (आप / ଆପଣ) — never तू/tum in system copy.
- Relative dates ("kal", "parso", "agle [weekday]") are ambiguous: the resolver picks the future interpretation and the agent must echo weekday + date for user confirmation before any booking tool call.
- Times render colloquially but unambiguously: "4:00 PM (shaam)" style.
- All prices are quoted +18% GST; invoices carry Xolver GSTIN + SAC code.

## Messaging & data constraints

- WhatsApp: free-form replies only inside the 24-hour customer service window; outside it, pre-approved utility templates only (tracked by `channels/whatsapp.py`). No marketing templates in v1. BSP/Meta Cloud API only — never unofficial WhatsApp libraries.
- Data residency: India region (ap-south-1) only. Phone numbers CSFLE-encrypted; audit log append-only with 90-day default TTL; media purged at 30 days; DPDP erasure pipeline SLA ≤7 days.
- Structured JSON logs with `tenant_id`/`conversation_id` on every line. The daily per-tenant cost report (LLM + Meta + telephony) is a launch blocker, not optional.
