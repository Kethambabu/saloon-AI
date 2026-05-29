# 🏗️ SalonAI Complete Architecture with Supabase

## 🌐 Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  React 18.2 + TypeScript 5.2                                                │
│  ├─ React Router v7 (Navigation)                                            │
│  ├─ Zustand 4.4.7 (Global State)                                            │
│  ├─ Axios 1.6.5 (API Client)                                                │
│  ├─ Tailwind CSS 3.4.3 (Styling)                                            │
│  └─ Recharts (Visualizations)                                               │
│                                                                              │
│  Components Structure:                                                       │
│  ├─ Layout (Sidebar, Header, Footer)                                        │
│  ├─ Pages (Dashboard, Bookings, Staff, Services)                            │
│  ├─ Hooks (useApi, useAuth, useNotification)                                │
│  └─ Store (authStore, bookingStore, uiStore)                               │
│                                                                              │
│  Running on: http://localhost:5173                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                   ↓ HTTP/REST API
                    (Request & Response in JSON)
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  FastAPI 0.104.1 + Python 3.11                                              │
│  ├─ ASGI Server (Uvicorn)                                                   │
│  ├─ Authentication & Authorization                                          │
│  ├─ Request Validation (Pydantic)                                           │
│  └─ Error Handling & Logging                                                │
│                                                                              │
│  API Routes Structure:                                                       │
│  ├─ /api/v1/auth (Login, Register, Token Refresh)                           │
│  ├─ /api/v1/branches (Salon Locations CRUD)                                 │
│  ├─ /api/v1/staff (Employees CRUD)                                          │
│  ├─ /api/v1/services (Services CRUD)                                        │
│  ├─ /api/v1/appointments (Bookings CRUD)                                    │
│  ├─ /api/v1/customers (Clients CRUD)                                        │
│  ├─ /api/v1/leads (Prospects CRUD)                                          │
│  ├─ /api/v1/reviews (Feedback CRUD)                                         │
│  ├─ /api/v1/agent (AI Agent Chat)                                           │
│  └─ /api/v1/health (Health Check)                                           │
│                                                                              │
│  Running on: http://localhost:8000                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                   ↓ SQL Queries
                    (SQLAlchemy ORM → PostgreSQL)
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATABASE LAYER (SUPABASE)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL 15 (Managed on Supabase)                                         │
│                                                                              │
│  Connection Configuration:                                                   │
│  ├─ Host: aws-1-ap-southeast-1.pooler.supabase.com                          │
│  ├─ Port: 6543 (Pooled) or 5432 (Direct)                                    │
│  ├─ SSL/TLS: REQUIRED                                                       │
│  ├─ Connection Pooler: PgBouncer                                            │
│  └─ Max Connections: 20 (with 10 overflow)                                  │
│                                                                              │
│  Tables (8 Total):                                                           │
│  ├─ branches (4 records - Salon locations)                                  │
│  ├─ staff (11+ records - Employees)                                         │
│  ├─ services (6 records - Salon offerings)                                  │
│  ├─ appointments (100+ records - Bookings)                                  │
│  ├─ customers (8+ records - Clients)                                        │
│  ├─ leads (10+ records - Prospects)                                         │
│  ├─ reviews (20+ records - Feedback)                                        │
│  └─ users (with roles: ADMIN, OWNER, MANAGER, STAFF, CUSTOMER)              │
│                                                                              │
│  Features:                                                                   │
│  ├─ UUID Primary Keys                                                       │
│  ├─ Timezone-aware Timestamps (created_at, updated_at)                      │
│  ├─ Foreign Key Relationships with CASCADE                                  │
│  ├─ Enum Constraints (Appointment Status, Lead Status, etc.)                │
│  ├─ Indexes for Performance                                                 │
│  ├─ Row-Level Security (RLS) enabled                                        │
│  ├─ Automated Backups                                                       │
│  └─ Read Replicas (Enterprise)                                              │
│                                                                              │
│  Running on: https://[project].supabase.co                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request/Response Flow

### Example: Get All Branches

```
┌─── FRONTEND (React) ─────────────────────────────────────────┐
│                                                              │
│  User Action: Click "View Branches"                          │
│                                                              │
│  Code:                                                       │
│  const { data, loading } = useApi('/branches', 'GET')        │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP GET Request
                   ↓ {"headers": {"Authorization": "Bearer token"}}
┌─── BACKEND (FastAPI) ─────────────────────────────────────────┐
│                                                              │
│  Route: @router.get("/branches")                             │
│                                                              │
│  Processing:                                                 │
│  1. Validate Bearer Token                                   │
│  2. Get Database Session                                    │
│  3. Query Branch Table                                      │
│  4. Serialize to JSON                                       │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ SQL Query
                   ↓ SELECT * FROM branches
┌─── DATABASE (Supabase PostgreSQL) ────────────────────────────┐
│                                                              │
│  Query:                                                      │
│  SELECT id, name, code, address, city, is_active,            │
│         created_at, updated_at                               │
│  FROM branches                                               │
│  ORDER BY name ASC                                           │
│                                                              │
│  Result: [{id, name, code, ...}, ...]                        │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ Row Data
                   ↓ [SQLAlchemy Model Objects]
┌─── BACKEND (FastAPI) ─────────────────────────────────────────┐
│                                                              │
│  Serialization:                                              │
│  [                                                           │
│    {                                                         │
│      "id": "550e8400-e29b-41d4-a716-446655440000",          │
│      "name": "Downtown Salon",                              │
│      "code": "DOWNTOWN",                                    │
│      "address": "123 Main St",                              │
│      "city": "New York",                                    │
│      "is_active": true,                                     │
│      "created_at": "2026-05-28T10:00:00Z",                 │
│      "updated_at": "2026-05-28T10:00:00Z"                  │
│    },                                                        │
│    ...                                                       │
│  ]                                                           │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP 200 OK Response
                   ↓ {"data": [...], "status": "success"}
┌─── FRONTEND (React) ─────────────────────────────────────────┐
│                                                              │
│  State Update:                                               │
│  setData(response.data)                                      │
│                                                              │
│  Re-render:                                                  │
│  branches.map(b => (                                         │
│    <BranchCard key={b.id} branch={b} />                      │
│  ))                                                          │
│                                                              │
│  Display: Branch list rendered on screen                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: HTTPS/TLS Encryption                              │
│  ├─ All communication encrypted in transit                  │
│  ├─ SSL certificates (production)                           │
│  └─ Applies to: Frontend ↔ Backend, Backend ↔ Supabase      │
│                                                              │
│  Layer 2: Authentication (JWT Tokens)                       │
│  ├─ User login → Server returns JWT token                  │
│  ├─ Token stored in frontend localStorage                  │
│  ├─ Token included in Authorization header                 │
│  ├─ Backend validates token on each request                │
│  └─ Token expiry & refresh mechanism                       │
│                                                              │
│  Layer 3: Authorization (Role-Based Access Control)         │
│  ├─ ADMIN - Full system access                             │
│  ├─ OWNER - Salon configuration                            │
│  ├─ MANAGER - Staff & booking management                   │
│  ├─ STAFF - Own appointments & availability                │
│  └─ CUSTOMER - Own bookings only                           │
│                                                              │
│  Layer 4: Database Level Security                          │
│  ├─ Row-Level Security (RLS) policies                      │
│  ├─ Column-level permissions                               │
│  ├─ Encrypted passwords (bcrypt)                           │
│  └─ Service role key for admin operations                  │
│                                                              │
│  Layer 5: Input Validation                                 │
│  ├─ Pydantic models validate request data                  │
│  ├─ Type checking on all fields                            │
│  ├─ Length & format validation                             │
│  └─ SQL injection prevention                               │
│                                                              │
│  Layer 6: Rate Limiting & DDoS Protection                  │
│  ├─ Supabase edge network                                  │
│  ├─ CloudFlare DDoS protection                             │
│  └─ API rate limiting (future enhancement)                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 💾 Data Flow Diagram

```
User Interaction
      ↓
┌─────────────────────┐
│  Frontend State     │
│  (Zustand Store)    │
└────────┬────────────┘
         ↓
┌─────────────────────┐       ┌──────────────────────┐
│  useApi Hook        │──────→│  Axios HTTP Client   │
│  (Custom Hook)      │       │  (Request Interceptor)
└────────┬────────────┘       └──────────────────────┘
         ↓                              ↓
┌─────────────────────┐       ┌──────────────────────┐
│  FastAPI Router     │←──────│  Backend API Server  │
│  (Route Handler)    │       │  (Response Handler)  │
└────────┬────────────┘       └──────────────────────┘
         ↓
┌─────────────────────┐
│  SQLAlchemy Session │
│  (ORM Mapper)       │
└────────┬────────────┘
         ↓
┌─────────────────────┐
│  PostgreSQL Driver  │
│  (psycopg2)         │
└────────┬────────────┘
         ↓
┌─────────────────────┐
│  Connection Pool    │
│  (PgBouncer)        │
└────────┬────────────┘
         ↓
┌─────────────────────┐
│  Supabase Database  │
│  (PostgreSQL 15)    │
└─────────────────────┘
```

---

## 📊 Deployment Architecture

### Development (Local)

```
Developer's Machine
├─ Frontend: npm run dev (Vite - :5173)
├─ Backend: uvicorn main:app --reload (Uvicorn - :8000)
└─ Database: Supabase Cloud PostgreSQL
```

### Production (Docker Compose)

```
┌─────────────────────────────────────┐
│         Docker Network              │
├─────────────────────────────────────┤
│  ┌──────────────────────────────┐   │
│  │ Nginx Reverse Proxy (:80)    │   │
│  │ - Routes to services         │   │
│  │ - Static files serving       │   │
│  └──────────────────────────────┘   │
│           ↓              ↓            │
│  ┌──────────────────────────────┐   │
│  │ Frontend Container           │   │
│  │ - React build + server       │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ Backend Container            │   │
│  │ - FastAPI app (Uvicorn)      │   │
│  │ - Agents, RAG, Database ORM  │   │
│  └──────────────────────────────┘   │
│           ↓                           │
│  ┌──────────────────────────────┐   │
│  │ Supabase (External)          │   │
│  │ - PostgreSQL 15              │   │
│  │ - Connection pooling         │   │
│  └──────────────────────────────┘   │
│                                      │
└─────────────────────────────────────┘
```

### Production (Kubernetes)

```
┌────────────────────────────────────────┐
│      Kubernetes Cluster                 │
├────────────────────────────────────────┤
│  Namespace: salonai                    │
│                                         │
│  ┌─ Ingress (Load Balancer)           │
│  │  └─ SSL/TLS Termination            │
│  │                                     │
│  ├─ Frontend Pod × 3 (Replicas)       │
│  │  └─ React + Nginx                  │
│  │                                     │
│  ├─ Backend Pod × 3 (Replicas)        │
│  │  └─ FastAPI + Uvicorn              │
│  │                                     │
│  ├─ Service: frontend (ClusterIP)     │
│  ├─ Service: backend (ClusterIP)      │
│  │                                     │
│  └─ ConfigMaps & Secrets               │
│     └─ Environment variables           │
│                                         │
│  External:                              │
│  └─ Supabase PostgreSQL               │
│                                         │
└────────────────────────────────────────┘
```

---

## 🔧 Technology Stack Summary

| Layer | Component | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | React | 18.2 | UI Framework |
| | TypeScript | 5.2 | Type Safety |
| | Vite | 5.2 | Build Tool |
| | Zustand | 4.4.7 | State Management |
| | Axios | 1.6.5 | HTTP Client |
| | Tailwind CSS | 3.4.3 | Styling |
| **Backend** | FastAPI | 0.104.1 | Web Framework |
| | Python | 3.11 | Language |
| | SQLAlchemy | 2.0.23 | ORM |
| | Pydantic | 2.5 | Validation |
| | Alembic | 1.12.1 | Migrations |
| | Uvicorn | 0.24.0 | ASGI Server |
| **Database** | PostgreSQL | 15 | Database |
| | Supabase | Managed | Hosting |
| | PgBouncer | - | Connection Pool |
| | psycopg2 | 2.9.9 | Driver |
| **AI** | AutoGen | 0.2.0 | Agent Framework |
| | Groq | - | LLM Provider |
| | LangChain | 0.1.0 | LLM Integration |
| **DevOps** | Docker | - | Containerization |
| | Docker Compose | - | Orchestration |
| | Kubernetes | - | Production Orchestration |
| | Nginx | - | Reverse Proxy |

---

## 🚀 Deployment Timeline

| Environment | Setup Time | Status |
|-------------|-----------|--------|
| Local Development | 5 minutes | ✅ Ready |
| Docker Development | 10 minutes | ✅ Ready |
| Docker Production | 20 minutes | ✅ Ready |
| Kubernetes | 30 minutes | ✅ Ready |
| Cloud (Heroku/Railway) | 15 minutes | ✅ Ready |

---

## 📝 Key Decisions

1. **Supabase PostgreSQL** - Managed database reduces operational overhead
2. **SQLAlchemy ORM** - Type-safe, maintainable database access
3. **FastAPI** - High-performance, modern Python framework
4. **React + Zustand** - Lightweight, scalable frontend
5. **JWT Tokens** - Stateless authentication, scalable
6. **Connection Pooling** - Optimized for Supabase's infrastructure
7. **Alembic Migrations** - Version-controlled schema changes
8. **Docker** - Consistent environments across machines

---

## 🔄 Development Workflow

```
1. Feature Planning
   ↓
2. Database Schema Design
   ↓
3. Create Alembic Migration
   ↓
4. Update SQLAlchemy Models
   ↓
5. Implement Backend API Routes
   ↓
6. Test with curl/Postman
   ↓
7. Build Frontend Components
   ↓
8. Integrate with useApi Hook
   ↓
9. End-to-End Testing
   ↓
10. Deploy to Production
    ↓
11. Monitor & Debug
```

---

## ✅ Status

- ✅ **Frontend**: React app ready for components
- ✅ **Backend**: FastAPI with AI agents
- ✅ **Database**: Supabase PostgreSQL with 8 tables
- ✅ **Migrations**: Alembic for schema management
- ✅ **Authentication**: JWT + Role-based access control
- ✅ **Deployment**: Docker & Kubernetes ready
- ✅ **Documentation**: Complete setup guides
- ✅ **Verification**: Automated health checks

🎉 **System is production-ready!**
