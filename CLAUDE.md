
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SalonAI Workforce Platform — a multi-agent AI system for salon operations. FastAPI backend (Python) + React/Vite frontend (TypeScript), talking to a Supabase-hosted Postgres database in production (falls back to local SQLite in dev/test). Six specialized AI agents (built on Microsoft AutoGen) handle bookings, CRM/leads, upsells, reputation/reviews, staff assistance, and business intelligence, routed through a central orchestrator.

Two docs at the repo root/backend go deep on architecture if you need more than the summary below: `KETHAM_ARCHITECTURE.md` (accurate, matches current code) and `backend/balu.md` (**stale** — describes a pre-refactor layout with `agents/`, `db/`, `domain/`, `handlers/`, `tools/` at the backend root; the real layout now nests these under `ai/`, `infrastructure/`, `application/`, `core/` — don't trust balu.md's file paths).

## Commands

### Backend (from `backend/`, with venv activated)
```
uvicorn main:app --reload --host 127.0.0.1 --port 8000   # run dev server (or run_backend.bat from repo root)
alembic upgrade head                                         # apply DB migrations (run from repo root; alembic.ini points at backend/infrastructure/db/migrations)
```
Tests force `ENVIRONMENT=testing` and `DATABASE_URL=sqlite:///./test.db` in `tests/conftest.py`, and shim legacy module paths (`agents.*`, `tools.*`, `services.*`, `rag.*`) onto the current `ai.*`/`application.*`/`infrastructure.*` locations for backward compatibility — don't be surprised to see those old names imported in test files.

### Frontend (from `frontend/`)
Standard npm scripts — see `package.json`'s `scripts` block (`dev`, `build`, `lint`, `lint:fix`, `format`, `format:check`, `type-check`).

### Whole-repo
`start.ps1` (PowerShell) or `run_backend.bat` / `run_frontend.bat` (repo root) launch both dev servers. `setup.bat` bootstraps the Python venv + npm install + `.env` from `.env.example`. There is no Docker/WSL requirement — everything runs Windows-native, with Supabase as the only external data dependency (see `supabase_init.sql` for schema bootstrap and required storage buckets).

## Architecture

### Request flow
`Frontend (React)` → `POST /api/agent/chat` (JWT-authenticated) → `MultiAgentOrchestrator` (`backend/ai/orchestrator.py`) → one of 6 AutoGen agents → a `*_workflow_v2` tool call → `WorkflowRegistry` dispatch → a `Handler` → an `application/services/*` service → SQLAlchemy → DB, publishing domain events along the way.

The orchestrator (`ai/orchestrator.py`) is the single canonical engine — despite what `balu.md` says about three orchestrator versions, that history has been unified into this one file. Per request it: checks cache (analytics only) → enforces role permissions → tries a fast path for greetings/farewells → loads session state (last 6 turns from `conversation_sessions`) → resolves names to entity UUIDs → detects intent (keyword rules → sticky booking state → LLM classifier fallback) → enforces role-vs-intent rules (CUSTOMER can't reach BUSINESS_INTELLIGENCE, etc.) → builds an enriched prompt (system time, customer context, history, RAG context, token-budget trimmed) → runs the selected AutoGen agent → saves the session turn.

Context propagation across async agent/tool calls uses `contextvars.ContextVar` (`current_user_role`, `current_user_id`, `current_tenant_id_var`) — this is what keeps concurrent requests from bleeding role/tenant state into each other.

**The 6 agents are built inline in `orchestrator.py`, not from `ai/agents/*.py`.** `MultiAgentOrchestrator._build_agents()` constructs each agent as a plain AutoGen `AssistantAgent`, with its system prompt pulled from the `_PHASE2_SYSTEM_PROMPTS` dict (also in `orchestrator.py`) and its tool set built from a locally-redefined `*_workflow_v2` wrapper that pulls `role`/`tenant_id`/`user_id`/`customer_id` off the contextvars above before forwarding to the real dispatch function in `ai/tools/capabilities.py`. The `Agent` subclasses living in `backend/ai/agents/*.py` (`ReceptionistAgent`, `BIAgent`, `LeadFollowupAgent`, `ReputationAgent`, `StaffAssistantAgent`, `UpsellAgent`) are **never instantiated in production** — each is exercised only by its own dedicated test file (e.g. `ReceptionistAgent` only by `test_booking_state_machine.py`, `test_receptionist_booking_flow.py`, `test_receptionist_agent.py`, `test_production_receptionist.py`, `test_leave_and_future_schedule.py`). If you're chasing a live-behavior bug, edit `_PHASE2_SYSTEM_PROMPTS` / `_build_agents()` in `orchestrator.py`, not the agent class files — changes there don't reach production. `ai/agents/receptionist_agent.py` in particular contains a large, fully-featured deterministic booking state machine (`ReceptionistAgent.process()`) that looks like the real booking flow but is dead code end-to-end.
  - Exception: `bi_agent.py`, `lead_followup_agent.py`, `reputation_agent.py`, and `upsell_agent.py` each still export live, standalone module-level functions (separate from their unused `Agent` class) that real code imports — e.g. `bi_agent.py`'s `get_dashboard_summary`, `forecast_revenue`, `generate_ai_insights`, etc. are used by `core/handlers.py` and `application/services/analytics_service.py`; the CRM/reputation/upsell equivalents are used by `ai/tools/transaction_dispatcher.py` and `ai/tools/mcp_tool.py`. So don't delete those files — just don't expect their `Agent` classes to be live.

### The 6 agents and their tools
| Agent (production name) | Live system prompt | Tool dispatch (`ai/tools/capabilities.py`) |
|---|---|---|
| Clara — Receptionist | `_PHASE2_SYSTEM_PROMPTS["Clara_Receptionist"]` | `appointment_workflow_v2` |
| Mia — Lead Follow-up | `_PHASE2_SYSTEM_PROMPTS["Mia_LeadFollowup"]` | `crm_workflow_v2` |
| Max — Upsell | `_PHASE2_SYSTEM_PROMPTS["Max_Upsell"]` | `recommendation_workflow_v2` |
| Olivia — Reputation | `_PHASE2_SYSTEM_PROMPTS["Olivia_Reputation"]` | `reputation_workflow_v2` |
| Atlas Staff | `_PHASE2_SYSTEM_PROMPTS["Atlas_Staff"]` | `staff_workflow_v2` |
| Atlas BI | `_PHASE2_SYSTEM_PROMPTS["Atlas_BI"]` | `analytics_workflow_v2` |

All 6 prompts live together near the top of `ai/orchestrator.py`. Each `*_workflow_v2` tool takes `(action, params)`, and (via the wrapper described above) dispatches through `core/workflow_registry.py` → a `Handler` class in `core/handlers.py` → an `application/services/*` service. Entity names ("Alice Smith", "Main Salon") get resolved to DB UUIDs via `application/services/entity_resolver_service.py` before hitting a service — never assume a param is already a UUID.

### Datetime handling in the booking path (past-date/time rejection)
`application/services/datetime_validation.py::validate_appointment_datetime()` is the single source of truth for "is this appointment date/time in the past" and is checked redundantly at three layers on the live path: `ai/tools/capabilities.py::_dispatch()` (short-circuits before the Handler even runs, for `check_availability`/`book`/`reschedule` actions), `core/handlers.py` Handlers, and again inside `application/services/appointment_service.py`/`availability_service.py`. Everything in this path must compare against `datetime.now(timezone.utc)` — never naive local server time. A prior bug had `availability_service.py`'s slot-filtering compare a naive `datetime.datetime.now()` (local server time) against a UTC-based slot grid, silently mis-filtering "already passed" slots by the server's UTC offset; watch for that pattern (`datetime.now()` without `timezone.utc`) anywhere new datetime comparisons get added to this path.

### MCP — the data-access gatekeeper
Anything agents read/write from the DB is meant to flow through `backend/mcp/` (`salon_mcp.py` for reads, `salon_mcp_write.py` for writes), not raw SQLAlchemy calls from tool code. The pipeline, in order: rate limiter (`rate_limiter.py`) → role permission check (`permissions.py`, `ROLE_PERMISSIONS`) → query guard (`query_guard.py`, injects mandatory row-level filters — e.g. CUSTOMER queries get `customer_id = current_user_id` auto-injected) → cache (`cache.py`) → the actual SQLAlchemy query → metrics (`metrics.py`) → audit log (`audit_log.py`).

### RAG — 5 knowledge domains
`infrastructure/rag/enterprise_rag.py` manages 5 FAISS-backed domains: `POLICY_RAG` (hours/FAQs/cancellation), `CUSTOMER_RAG` (preferences/history), `STAFF_RAG`, `LEAD_RAG`, `BUSINESS_RAG`. Intent determines which domain(s) get injected into the prompt. Indices live under `backend/data/faiss_indices/<domain>/`; missing index files fail gracefully (warn-once, not an error). `infrastructure/rag/rag_unified.py` is the unified `search_knowledge_base()` entry point agents call.

### Events
Domain services publish events (e.g. `AppointmentBookedEvent`) through the in-process `EventBus` (`infrastructure/events/event_bus.py`), persisted first to the `outbox_events` table (outbox pattern, so a crash mid-flight doesn't lose the event). `AnalyticsService` and `NotificationService` subscribe and react; `MemoryCuratorService` also subscribes to extract durable facts (allergies, preferences) into `curated_memories`.

### Security layers (in request order)
CORS whitelist → JWT auth (`api/deps.py`, `core/security.py`; HS256, bcrypt passwords, short-lived access token + longer refresh token) → RBAC (role vs. allowed agents: CUSTOMER→booking/reputation/upsell, STAFF→+staff, MANAGER/OWNER/ADMIN→all) → MCP permission check → query-guard row-level security → placeholder/prompt-injection detection on LLM-produced params (rejects hallucinated UUIDs like `"customer_id"` used literally) → tenant isolation via contextvars.

### LLM providers
Multi-provider fallback chain managed by `core/llm_config.py`, unified behind an OpenAI-compatible interface in `core/openai_client_adapter.py` so agent code never branches on provider: Groq (`llama-3.3-70b-versatile` primary, `llama-3.1-8b-instant` fallback) → HuggingFace (`Qwen/Qwen2.5-72B-Instruct` via router) → Gemini (`gemini-2.0-flash`). Keys come from `.env` (`GROQ_API_KEY`, `HUGGINGFACE_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`).

### Database
SQLAlchemy models in `backend/infrastructure/db/models.py`; all models extend a `BaseModel` providing UUID PK + `created_at`/`updated_at`. `infrastructure/db/database.py` connects to `DATABASE_URL` (Supabase pooler in prod) and falls back to local SQLite if unreachable. Schema is auto-created + seeded on startup in dev/test only (`main.py` lifespan); production uses Alembic migrations (`alembic upgrade head`, migrations under `backend/infrastructure/db/migrations`). Key tables: `appointments`, `leads`, `reviews`, `outbox_events`, `conversation_sessions` (multi-turn chat memory), `curated_memories` (long-term agent memory).

### Folder map (backend)
```
backend/
  main.py                     # FastAPI app factory + startup lifespan (LLM validation, DB init/seed, service init, APScheduler)
  ai/
    orchestrator.py           # MultiAgentOrchestrator — canonical, single orchestration engine; also where the 6 live agent prompts/tools are actually built (_build_agents, _PHASE2_SYSTEM_PROMPTS)
    agents/                   # 6 Agent subclasses — their classes are NOT used in production (test-only); some files still export live standalone helper functions used elsewhere (see Request flow)
    tools/capabilities.py     # the 6 *_workflow_v2 tool entry points
    workflows/                # thin per-domain workflow facades (legacy Phase 1 style)
  api/routes/                 # FastAPI route modules, one per domain area
  application/services/       # business logic — appointment/analytics/lead/review/staff/loyalty/etc.
  core/                       # config, security (JWT), workflow_registry, capability_registry, handlers, tenant_context, llm_config
  infrastructure/
    db/                       # SQLAlchemy engine, models, seed data, alembic migrations
    events/event_bus.py       # in-process pub/sub, outbox pattern
    rag/                      # FAISS ingestion/retrieval, 5-domain enterprise RAG
    cache/                    # response cache, token/context budget compression
  mcp/                        # rate limiting, permissions, query guard, cache, metrics, audit log
  tests/                      # pytest suite; conftest.py shims legacy import paths
```

Background jobs (APScheduler, non-production only): lead follow-up sweep and returning-customer cohort reminders, both every 60 minutes (`main.py` lifespan).

## Notes
- `backend/.env` and root `.env` hold secrets (`SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`/provider keys, Supabase creds) — `core/config.py` loads both, backend `.env` taking precedence via `pydantic-settings`.
- Test credentials seeded by `supabase_init.sql`/`infrastructure/db/seed.py`: `owner@salonai.com`, `manager@salonai.com`, `marcus@salonai.com`, `customer@example.com`, all password `password123`.
- A `prisma/schema.prisma` exists at the repo root and in `frontend/` but the actual DB access layer is SQLAlchemy/Alembic on the Python side — treat Prisma files as auxiliary/unused unless you find code that actually imports the generated client.
