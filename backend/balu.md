# 🏗️ SalonAI Backend — Full Architecture Blueprint (balu.md)

A complete, in-depth picture of every subsystem in the SalonAI Workforce backend: how they are structured, how they talk to each other, and where every file lives.

---

## 📦 Repository Layout

```
backend/
├── main.py                  ← FastAPI entry point + lifespan startup
├── agents/                  ← All AI agents (AutoGen-powered)
├── api/
│   └── routes/              ← FastAPI HTTP route handlers (15 route files)
├── core/                    ← Cross-cutting infrastructure (LLM, registry, events)
├── db/                      ← SQLAlchemy models, database connection, seeder
├── domain/                  ← Pure-domain service layer (business logic, events)
├── handlers/                ← Workflow handlers dispatched by WorkflowRegistry
├── mcp/                     ← Model Context Protocol — gated data access layer
├── rag/                     ← RAG pipeline: embed, ingest, retrieve
├── services/                ← Application services (memory, analytics, recommendations)
├── tools/                   ← Low-level tool functions called by agents
├── utils/                   ← Shared helpers (entity resolver, etc.)
├── workflows/               ← Workflow facades used in Phase 1 agent calls
└── data/
    ├── faiss/               ← Per-tenant, per-domain FAISS vector indices
    └── salon_local.db       ← SQLite fallback database
```

---

## 🚀 1. Startup — main.py

`main.py` is the FastAPI **application factory and startup controller**. It runs in four stages inside the `lifespan()` async context manager:

| Stage | What happens |
|-------|-------------|
| **LLM Validation** | `validate_llm_startup()` — confirms GROQ / HuggingFace API keys work |
| **DB Init** | `check_db_health()` then `Base.metadata.create_all()` then `seed_database()` if empty |
| **Domain Services** | Instantiates all 8 domain services; registers EventBus subscribers |
| **APScheduler** | Starts 4 recurring jobs: leads (60 min), cohort reminders (60 min), daily memory (23:59), weekly memory (Sun 23:59) |

```
main.py
  └── lifespan()
       ├── validate_llm_startup()          [core/llm_config.py]
       ├── db.database.check_db_health()   [db/database.py]
       ├── db.models.Base.create_all()     [db/models.py]
       ├── domain.<service>.get_*()        [domain/]
       ├── register_event_subscribers()    [domain/analytics_service.py]
       └── APScheduler — 4 jobs
```

---

## 🗄️ 2. Database Layer — db/

| File | Purpose |
|------|---------|
| `db/database.py` | SQLAlchemy engine with auto-fallback to SQLite if Supabase is unreachable |
| `db/models.py` | All 20+ ORM table models (User, Branch, Staff, Customer, Appointment, Service, Lead, Review, ChatLog, Loyalty, AgentMemory, BusinessMetricsHistory, etc.) |
| `db/seed.py` | Full DB seeder — creates 1 branch, 6 services, 4 staff, 6 user accounts |

### Connection Strategy
```
DATABASE_URL (Supabase Pooler port 6543)
  → success: Use PostgreSQL (live Supabase)
  → fail:    Fall back to SQLite at data/salon_local.db
```

### Key ORM Models
```
User           → Staff OR Customer (role-based link)
Branch         → Services, Staff, Appointments
Appointment    → Customer + Staff + Service + Branch
Lead           → Customer (optional), Agent-assigned pipeline
Review         → Customer + Staff + Appointment
ChatLog        → links user session conversation turns
AgentMemory    → per-agent FAISS memory snapshots
BusinessMetricsHistory → BI KPI snapshots
```

---

## 🤖 3. Agents Layer — agents/

Six specialized AI agents built on **Microsoft AutoGen** (SelectorGroupChat pattern):

| Agent | File | Role |
|-------|------|------|
| **Clara** – Receptionist | `receptionist_agent.py` (123 KB) | Books/cancels/reschedules appointments, checks availability, handles FAQs via RAG |
| **Mia** – Lead Follow-up | `lead_followup_agent.py` | Manages CRM pipeline, generates personalized follow-up messages |
| **Max** – Upsell | `upsell_agent.py` | Recommends add-on services based on customer history |
| **Olivia** – Reputation | `reputation_agent.py` | Monitors and responds to reviews, manages brand perception |
| **Atlas Staff** | `staff_assistant_agent.py` | Staff scheduling, performance analytics, task management |
| **Atlas BI** | `bi_agent.py` | Business intelligence, SQL queries, KPI analysis |

### Agent Evolution — Three Orchestrator Versions

```
orchestrator.py    ← Phase 1: Basic SelectorGroupChat, if/else dispatch
orchestrator_v2.py ← Phase 1+: AgentIntent enum, fast-path canned responses, role validation
orchestrator_v3.py ← Phase 2: WorkflowRegistry + CapabilityRegistry + TenantContext + EventBus + 5-domain RAG
```

The public-facing `agents/__init__.py` exposes:
```python
MultiAgentOrchestrator   # orchestrator.py (legacy, backward compatible)
get_phase1_orchestrator  # Phase 2 factory (orchestrator_v3.py wraps v2)
```

---

## 🎛️ 4. Orchestration — Phase 2 Architecture (Orchestrator V3)

`agents/orchestrator_v3.py` is the **Phase 2 brain**. Every incoming chat request flows through 8 sequential stages:

```
HTTP Request (/api/v1/chat)
        |
        v
[1] TenantContext isolation          ← core/tenant_context.py
        |  Set current_tenant_id, plan, feature flags per request
        v
[2] Enterprise Permission check      ← services/enterprise_permission.py
        |  Validate role + plan gating (ENTERPRISE feature gate)
        v
[3] Token Budget enforcement         ← core/token_optimizer.py
        |  Hard cap: 3000 tokens on context; compress if exceeded
        v
[4] ResultCache lookup (hot path)    ← core/token_optimizer.py
        |  Cache key: hash(agent_name + query). If hit skip LLM
        v
[5] WorkflowRegistry dispatch        ← core/workflow_registry.py
        |  Maps (workflow_name, action) to Handler class
        v
[6] CapabilityRegistry resolution    ← core/capability_registry.py
        |  Maps agent name to allowed capabilities to workflow
        v
[7] Agent execution (AutoGen)        ← agents/<specialist_agent>.py
        |  SelectorGroupChat selects agent, LLM call, tool calls
        v
[8] EventBus publish                 ← core/event_bus.py
           Fires domain events (appointment.booked, review.submitted, etc.)
```

### Context Variables (async-safe)
```python
current_user_role     = ContextVar("current_user_role")
current_user_id       = ContextVar("current_user_id")
current_tenant_id_var = ContextVar("current_tenant_id_var")
```
These propagate through every AutoGen agent tool call automatically.

---

## 🏗️ 5. Core Infrastructure — core/

| File | Purpose |
|------|---------|
| `config.py` | `Settings` Pydantic model — loads all .env variables |
| `llm_config.py` | Multi-LLM pool: GROQ (primary), HuggingFace (secondary), Gemini (tertiary) |
| `openai_client_adapter.py` | Custom OpenAIChatCompletionClient wrapping all LLM providers behind a unified OpenAI-compatible interface (56 KB) |
| `event_bus.py` | Thread-safe in-process EventBus. subscribe(event_type, handler) / publish(SalonEvent) |
| `capability_registry.py` | Maps agent capabilities to handler class paths, action keys, allowed roles, and workflow names |
| `workflow_registry.py` | Maps (workflow_name, action) to BaseHandler class. Pre-registers all 6 agent workflows |
| `tenant_context.py` | TenantContext dataclass + TenantRegistry + TenantIsolationGuard. Per-request isolation via contextvars |
| `token_optimizer.py` | TokenCompressor, ResultCache, BudgetEnforcer — keeps LLM context within 3000 tokens |
| `response_cache.py` | In-memory cache for hot agent responses |
| `security.py` | JWT token creation and verification |
| `logging.py` | Structured JSON logging setup |

### EventBus Domain Events
```
appointment.booked    → AnalyticsService.handle_appointment_booked_event
                      → NotificationService.handle_appointment_booked_event
lead.converted        → NotificationService.handle_lead_converted_event
review.submitted      → NotificationService.handle_review_submitted_event
```

---

## 🔐 6. MCP — Model Context Protocol (mcp/)

**SalonMCP** is the **central gatekeeper for ALL database access by agents**. Every data read/write from agents flows through MCP — never direct SQL.

### MCP Pipeline (7 stages per request)

```
Agent calls mcp_tool.py
        |
        v
[1] Rate Limiter          ← mcp/rate_limiter.py
        |  Token-bucket per agent role. Raises RateLimitExceeded if exceeded.
        v
[2] Permission Check      ← mcp/permissions.py
        |  ROLE_PERMISSIONS table:
        |    CUSTOMER → appointments, reviews, loyalty_points, services, branches, offers, knowledge
        |    STAFF    → appointments, staff, reviews, services, branches
        |    ADMIN    → * (all resources)
        v
[3] Query Guard           ← mcp/query_guard.py
        |  Injects mandatory filters (CUSTOMER can only see own rows)
        |  Sanitizes for SQL injection. Raises GuardViolationError on cross-tenant access.
        v
[4] Cache Lookup          ← mcp/cache.py
        |  In-memory dict keyed by (resource, filters_hash). TTL-based expiry.
        v
[5] SQLAlchemy DB Query   ← db/database.py + db/models.py
        |  ORM query → PostgreSQL (Supabase) or SQLite fallback
        v
[6] Metrics Collection    ← mcp/metrics.py
        |  Records query latency, hit rate, error rate per agent/resource
        v
[7] Audit Logging         ← mcp/audit_log.py
           Appends every read/write to an append-only audit trail
```

### MCP File Map

| File | Purpose |
|------|---------|
| `salon_mcp.py` | Core SalonMCP class — 9 get_*() methods + execute_write() |
| `salon_mcp_write.py` | SalonMCPWrite — insert/update/delete operations with UUID handling |
| `schemas.py` | MCPContext, MCPRequest, MCPResponse Pydantic models |
| `permissions.py` | ROLE_PERMISSIONS dict + check_permission() |
| `query_guard.py` | validate_and_sanitise(), GuardViolationError |
| `rate_limiter.py` | Token-bucket rate limiter per role |
| `cache.py` | In-memory query result cache |
| `metrics.py` | Query performance tracker |
| `audit_log.py` | Append-only audit logger |
| `resource_registry.py` | Registry of MCP-accessible resources |
| `context_builder.py` | Builds MCPContext from the authenticated User object |

### MCP Read API
```python
SalonMCP.get_appointments(context, filters, limit, offset)
SalonMCP.get_reviews(context, filters, limit, offset)
SalonMCP.get_services(context, filters, limit, offset)
SalonMCP.get_staff(context, filters, limit, offset)
SalonMCP.get_customers(context, filters, limit, offset)
SalonMCP.get_leads(context, filters, limit, offset)
SalonMCP.get_branches(context, filters, limit, offset)
SalonMCP.get_loyalty_points(context, filters, limit, offset)
SalonMCP.execute_write(context, resource, operation, data, filters)
```
All return MCPResponse(success, resource, operation, data, count, error, metadata).

---

## 📚 7. RAG System — rag/

The RAG (Retrieval-Augmented Generation) system gives agents **long-term semantic memory** and the ability to search the salon knowledge base.

### RAG Phase 2 — 5 Named Domains (rag/enterprise_rag.py)

```
POLICY_RAG    → receptionist_knowledge + salon_knowledge FAISS indices
                (Policies, FAQs, business hours, cancellation rules)

CUSTOMER_RAG  → customer_interactions + customer FAISS indices
                (Customer preferences, styling notes, interaction history)

STAFF_RAG     → staff FAISS index
                (Staff performance, expertise profiles, scheduling notes)

LEAD_RAG      → lead FAISS index
                (CRM playbooks, follow-up templates, nurturing notes)

BUSINESS_RAG  → bi_memory FAISS index
                (KPI history, BI memory, cohort snapshots)
```

Legacy domain names (e.g. "policies", "faq", "interactions") are auto-mapped to the correct Phase 2 domain via _LEGACY_DOMAIN_MAP.

### RAG Pipeline

```
[INGESTION]
Raw Data Sources
    ├── PostgreSQL DB (appointments, reviews, leads, chats)
    └── Static documents (services, policies, FAQs)
         |
         v
rag/ingest.py
    ├── DocumentChunker      — splits text into 500-char overlapping chunks
    ├── SalonKnowledgeBase   — builds static knowledge FAISS index
    ├── InteractionIndexer   — builds customer interaction FAISS index
    └── RAGIngestor          — unified facade for full pipeline

         | embedded using HuggingFace sentence-transformers (all-MiniLM-L6-v2)
         v
rag/embeddings.py → get_embedding_model()

         |
         v
data/faiss_indices/<domain>/
    e.g. data/faiss_indices/salon_knowledge/
         data/faiss_indices/customer_interactions/
         data/faiss_indices/bi_memory/

[RETRIEVAL]
rag/retriever.py
    ├── FAISSRetriever      — single-index retrieval with score thresholding (>=0.3)
    └── SalonRAGRetriever   — multi-index fusion retriever

         |
         v
rag/enterprise_rag.py
    └── search_knowledge_base(domain, query, top_k)
             ↑
        Called by orchestrator_v3 during agent tool execution
```

### Memory Pipeline — 28 FAISS Indices (services/memory_pipeline_service.py)

```
7 Agents x 4 Time Levels = 28 FAISS index directories

Agents: receptionist | customer | staff | lead | upsell | reputation | business_intelligence
Levels: daily | weekly | monthly | yearly

Daily Pipeline Flow:
  DB query (today's appointments/reviews/leads/chats)
      → LLM (GROQ) synthesizes narrative summary
      → Embed → Write to FAISS daily index
      → Store AgentMemory row in DB

Weekly Pipeline:
  Consolidates 7 daily summaries → LLM → FAISS weekly index
```

---

## ⚙️ 8. Workflows — workflows/

Workflows are thin facades used by Phase 1 agents to wrap tool calls:

| Workflow | Agent | Tools |
|---------|-------|-------|
| `appointment_workflow.py` | Clara | `booking_tools.py` |
| `crm_workflow.py` | Mia | `lead_tools.py` |
| `recommendation_workflow.py` | Max | `recommendation_tools.py` |
| `review_workflow.py` | Olivia | `review_tools.py`, `reputation_tools.py` |
| `staff_workflow.py` | Atlas Staff | `staff_tools.py` |
| `analytics_workflow.py` | Atlas BI | `bi_tools.py` |
| `notification_workflow.py` | All | notification dispatch |
| `booking_workflow.py` | Clara | high-level booking orchestration |

In Phase 2, the **WorkflowRegistry** replaces direct workflow calls with handler-based dispatch.

---

## 🔧 9. Tools Layer — tools/

| Tool File | What it does |
|-----------|-------------|
| `booking_tools.py` (54 KB) | book_new_appointment, cancel_appointment, reschedule_appointment, check_stylist_availability, get_customer_history |
| `lead_tools.py` (25 KB) | search_leads, create_lead, advance_lead, send_followup, generate_message, conversion_analytics |
| `staff_tools.py` (24 KB) | Staff scheduling, performance metrics, shift management |
| `reputation_tools.py` (23 KB) | Review fetching, sentiment analysis, response generation |
| `capability_tools.py` (33 KB) | Phase 1 tool wrappers for Phase 2 capability registry |
| `capability_tools_v2.py` (21 KB) | Updated Phase 2 capability tool wrappers |
| `bi_tools.py` (8 KB) | execute_bi_sql_query — safe SQL execution with LIMIT injection |
| `mcp_tool.py` (32 KB) | High-level agent-facing MCP wrapper — builds MCPContext from agent session |
| `receptionist_rag_tools.py` | search_knowledge_base() — Clara's RAG tool |
| `rag_unified.py` | Unified RAG tool wrapper for all agents |
| `recommendation_tools.py` | Upsell recommendation fetching |
| `loyalty_service.py` | Loyalty points calculation and award |
| `loyalty_triggers.py` | Event hooks that trigger loyalty awards |
| `discovery_tools.py` | Service/branch discovery for onboarding |
| `transaction_unified.py` | Unified transaction tool wrapper |
| `review_tools.py` | Review submission tools |

---

## 🏛️ 10. Domain Services — domain/

Domain services implement pure business logic without HTTP concerns. Initialized once at startup and communicate through the EventBus:

| File | Domain |
|------|--------|
| `appointment_service.py` | Create, cancel, reschedule appointments + availability |
| `analytics_service.py` | KPI tracking, metrics aggregation, EventBus subscriber |
| `availability_service.py` | Staff schedule and slot calculation |
| `customer_service.py` | Customer profile management |
| `lead_service.py` | CRM pipeline, lead scoring |
| `notification_service.py` | Multi-channel notification dispatch, EventBus subscriber |
| `review_service.py` | Review lifecycle management |
| `staff_service.py` | Staff profile and schedule management |

**Event Subscription Matrix:**
```
AppointmentBookedEvent  → AnalyticsService  (records booking KPI)
                        → NotificationService (sends confirmation)
LeadConvertedEvent      → NotificationService (sends conversion notification)
ReviewSubmittedEvent    → NotificationService (notifies owner)
```

---

## 🌐 11. API Routes — api/routes/

| Route File | Key Endpoints |
|-----------|--------------|
| `agent_routes.py` | POST /api/v1/chat, POST /api/v1/mcp-test |
| `auth_routes.py` | POST /login, GET /me, POST /refresh, POST /logout |
| `core_routes.py` | Health, services, appointments, dashboard, branches |
| `analytics_routes.py` | KPIs, revenue, cohort, staff performance |
| `staff_routes.py` | Staff profile, schedule, appointments |
| `customer_routes.py` | Customer dashboard, appointments, loyalty |
| `admin_knowledge_routes.py` | RAG knowledge upload, rebuild trigger |
| `memory_routes.py` | Daily/weekly memory snapshots, status |
| `mcp_routes.py` | MCP resource access test endpoints |
| `mcp_metrics_routes.py` | MCP performance metrics dashboard |
| `recommendation_routes.py` | Upsell recommendation management |
| `review_routes.py` | Review CRUD, sentiment analysis |
| `notification_routes.py` | Notification dispatch |
| `storage_routes.py` | File upload to Supabase Storage |

---

## 🔄 12. Full Request Data Flow — Booking Example

```
POST /api/v1/chat
  { "message": "Book a haircut tomorrow at 10 AM with Priya", "role": "CUSTOMER" }

1. auth_routes.py      → Validate JWT → Extract user (Customer role)
2. agent_routes.py     → Build request context
3. orchestrator_v3.py
   ├── TenantContext: branch_id, plan = STARTER
   ├── Permission check: CUSTOMER allowed for booking
   ├── Token budget enforce: 3000 token cap
   ├── ResultCache: MISS → proceed to LLM
   ├── WorkflowRegistry.dispatch("appointment_workflow_v2", "book")
   └── SelectorGroupChat → selects Clara

4. Clara (ReceptionistAgent)
   ├── LLM (GROQ llama-3.3-70b): "tomorrow" → "2026-07-18", "10 AM" → "T04:30:00Z"
   ├── appointment_workflow_v2(action="check_availability")
   │    └── booking_tools.check_stylist_availability()
   │         └── MCP → SalonMCP.get_appointments(CUSTOMER context)
   │              ├── RateLimiter: OK
   │              ├── Permission: OK (appointments in CUSTOMER allowed resources)
   │              ├── QueryGuard: injects customer_id filter
   │              ├── Cache: MISS → Supabase PostgreSQL query
   │              ├── Metrics recorded
   │              └── Audit logged
   ├── Receives slots → "10:00 AM with Priya available"
   ├── appointment_workflow_v2(action="book")
   │    └── booking_tools.book_new_appointment()
   │         └── MCP → SalonMCPWrite.execute_write(INSERT appointment)
   └── Formats confirmation response

5. EventBus.publish(AppointmentBookedEvent)
   ├── AnalyticsService → updates KPIs
   └── NotificationService → sends SMS/email confirmation

6. Nightly scheduler: interaction stored in FAISS
   → customer/daily/ index updated with booking narrative

Response: { "response": "Booked! Haircut with Priya on 18 July at 10:00 AM" }
```

---

## 📊 13. LLM Configuration — core/llm_config.py

```
Priority 1: GROQ API
    Model: llama-3.3-70b-versatile (primary)
           llama-3.1-8b-instant     (fallback)
    Key: GROQ_API_KEY

Priority 2: HuggingFace Inference API
    Model: Qwen/Qwen2.5-72B-Instruct
    Key: HUGGINGFACE_API_KEY

Priority 3: Gemini API
    Key: GEMINI_API_KEY

All wrapped by OpenAIChatCompletionClient (core/openai_client_adapter.py)
so agents never need to know which provider is active.
```

---

## 🔑 14. Authentication and Authorization

```
POST /api/v1/auth/login
    → validate email + bcrypt password
    → issue JWT access_token (30 min) + refresh_token (7 days)
    → store refresh_token in DB

Roles:
    ADMIN    → full access, all agents, all MCP resources, analytics
    STAFF    → booking, availability, own schedule, customer info (limited)
    CUSTOMER → own appointments, reviews, loyalty, service catalog
```

---

## 📋 15. Background Scheduler Jobs

```
APScheduler (BackgroundScheduler, started in main.py lifespan)

Job 1: process_leads()                        every 60 minutes
         Finds stale leads → AI follow-up → updates pipeline stage

Job 2: process_returning_cohort_reminders()   every 60 minutes
         Finds customers with upcoming events → sends reminders

Memory Curator (Event-Driven, Asynchronous)
         Triggered by domain events (e.g. customer preference, lead change, upsell outcome).
         Evaluates events through policy rules and LLM evaluation, saving approved facts to PostgreSQL and local per-tenant, per-domain FAISS indices.
         Note: Old daily/weekly hierarchical roll-up memory snapshots have been retired and removed.

```

---

## 🗺️ 16. Component Dependency Map

```
main.py
  ├── core/config.py
  ├── core/llm_config.py
  ├── core/logging.py
  ├── db/database.py (engine, fallback)
  ├── db/models.py (ORM)
  ├── db/seed.py (initial data)
  ├── domain/*_service.py (singletons)
  ├── core/event_bus.py (pub/sub)
  └── APScheduler
        ├── services/lead_service.py
        ├── services/analytics_service.py
        └── services/memory_pipeline_service.py → rag/

api/routes/ (HTTP)
  └── api/deps.py → core/security.py → db/models.py

agents/orchestrator_v3.py (Phase 2 brain)
  ├── core/workflow_registry.py
  ├── core/capability_registry.py
  ├── core/tenant_context.py
  ├── core/token_optimizer.py
  ├── core/event_bus.py
  ├── rag/enterprise_rag.py (5-domain RAG)
  └── agents/*_agent.py
        └── tools/*.py
              └── mcp/salon_mcp.py
                    ├── mcp/permissions.py
                    ├── mcp/query_guard.py
                    ├── mcp/rate_limiter.py
                    ├── mcp/cache.py
                    ├── mcp/metrics.py
                    └── mcp/audit_log.py
```

---

*Generated: 2026-07-17 | SalonAI Backend v0.1.0 | Python 3.12.4 + FastAPI + AutoGen + LangChain + FAISS*

