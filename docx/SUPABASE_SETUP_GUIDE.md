# 🗄️ Supabase Database Setup & Connection Guide

## Current Status: ✅ Configuration Ready

Your project already has Supabase configured! This guide helps you **verify & complete the connection**.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Current Configuration](#current-configuration)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Database Schema Initialization](#database-schema-initialization)
5. [Verification Checklist](#verification-checklist)
6. [How It Works](#how-it-works)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Project Overview

### Architecture

```
Frontend (React/TypeScript)
    ↓ (HTTP API calls)
FastAPI Backend
    ↓ (SQLAlchemy ORM)
Supabase PostgreSQL Database
```

### Tech Stack
- **Database**: PostgreSQL 15 (Supabase Managed)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Connection Pooling**: PgBouncer (via Supabase)
- **Python Driver**: psycopg2

---

## 🔧 Current Configuration

### Backend `.env` File (Already Set)

Your `.backend/.env` already contains:

```env
# ✅ Database Connection
DATABASE_URL="postgresql://postgres.[project]:[password]@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
DIRECT_URL="postgresql://postgres.[project]:[password]@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

# ✅ Supabase Service Keys
SUPABASE_URL=https://[project].supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Database Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `config.py` | Settings loader | `backend/core/config.py` |
| `database.py` | Connection manager | `backend/db/database.py` |
| `models.py` | ORM models | `backend/db/models.py` |
| `alembic.ini` | Migration config | `alembic.ini` |

---

## 🚀 Step-by-Step Setup

### Step 1: Verify Supabase Credentials

1. **Login to Supabase** (https://supabase.com)
2. **Navigate** to Settings → Database → Connection String
3. **Select** "Connection pooling" (6543) for APPLICATION use
4. **Copy** the pooled connection string
5. **Paste** into `.env` as `DATABASE_URL`

### Step 2: Install Dependencies

All required packages are already in `requirements.txt`:

```bash
# From project root
cd backend
pip install -r requirements.txt
```

**Key packages:**
- `sqlalchemy==2.0.23` - ORM
- `psycopg2-binary==2.9.9` - PostgreSQL driver
- `alembic==1.12.1` - Migration tool
- `supabase==2.3.5` - Supabase client

### Step 3: Initialize Database Schema

Run Alembic migrations to create tables:

```bash
cd backend
# Create tables from migration files
alembic upgrade head
```

This will:
- ✅ Create all tables (branches, staff, services, appointments, leads, reviews, users)
- ✅ Create indexes for performance
- ✅ Set up foreign key relationships
- ✅ Apply all constraints

### Step 4: Seed Initial Data (Optional)

```bash
cd backend
python -m db.seed
```

This creates:
- 4 salon branches
- 6 services
- 11+ staff members
- 8 customers
- Sample appointments

---

## 📊 Database Schema Initialization

### What Gets Created

When you run `alembic upgrade head`, these tables are created:

```
Branches (salons)
├── Locations across cities
├── Each with staff, services, bookings

Staff (employees)
├── Stylists, receptionists, managers
├── Assigned to branches
├── With availability schedules

Services (offerings)
├── Haircuts, styling, treatments
├── Price, duration, branch assignments

Appointments (bookings)
├── Customer + Staff + Service + Branch
├── Status tracking (PENDING, CONFIRMED, COMPLETED, CANCELLED, NO_SHOW)
├── Timestamps (created_at, updated_at)

Customers (clients)
├── Contact information
├── Booking history
├── Reviews/ratings

Leads (prospects)
├── New potential customers
├── Followup tracking
├── Conversion status

Reviews (feedback)
├── Ratings and comments
├── Moderation status
├── Branch association
```

### Connection Details

```python
# Supabase Connection Pool Settings (from database.py)
pool_size=20                # Max connections
max_overflow=10             # Extra connections when needed
pool_recycle=1800           # Recycle after 30 minutes
pool_pre_ping=True          # Health check on checkout
```

---

## ✅ Verification Checklist

### 1. Test Database Connection

```bash
cd backend

# Option A: Run health check in Python
python -c "from db.database import check_db_health; print(check_db_health())"
# Should print: True

# Option B: Test via backend API startup
uvicorn main:app --reload
# Should see: "Database health check: OK"
```

### 2. Verify Tables Exist

```bash
# Connect to Supabase with psql
psql "postgresql://postgres:[password]@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# List tables
\dt

# Should see:
# - public.branches
# - public.staff
# - public.services
# - public.appointments
# - public.leads
# - public.reviews
# - public.customers
# - public.users
```

### 3. Test API Endpoints

```bash
# Start backend (if not running)
cd backend
uvicorn main:app --reload

# In another terminal, test database connectivity
curl -X GET http://localhost:8000/api/v1/health

# Should return: {"status": "healthy", "database": "connected"}
```

### 4. Frontend Integration

```bash
# Start frontend
cd frontend
npm install
npm run dev

# Open http://localhost:5173
# Backend automatically uses environment DATABASE_URL
# Frontend calls API endpoints at http://localhost:8000/api/v1/*
```

---

## 🔌 How It Works

### Architecture Flow

```
┌─────────────────────────────────────────────────┐
│         Frontend (React/TypeScript)             │
│      http://localhost:5173                      │
└─────────────────┬───────────────────────────────┘
                  │ HTTP API Calls
                  ↓
┌─────────────────────────────────────────────────┐
│     FastAPI Backend                             │
│     http://localhost:8000/api/v1/*              │
│  - Routes handle HTTP requests                  │
│  - Use SQLAlchemy models                        │
└─────────────────┬───────────────────────────────┘
                  │ SQL Queries
                  ↓
┌─────────────────────────────────────────────────┐
│  Supabase PostgreSQL                            │
│  - Connection pooling (PgBouncer)               │
│  - SSL/TLS encryption                           │
│  - Automated backups                            │
│  - Read replicas (enterprise)                   │
└─────────────────────────────────────────────────┘
```

### Request Flow Example

```
1. Frontend: GET /api/v1/branches
2. Backend: @app.get("/branches")
3. Database: SELECT * FROM branches
4. Response: [...branch data...]
5. Frontend: Renders branch list
```

### Connection String Breakdown

```
postgresql://
├── User: postgres
├── Password: [your_password]
├── Host: aws-1-ap-southeast-1.pooler.supabase.com
├── Port: 6543 (pooled) or 5432 (direct)
└── Database: postgres
└── Mode: ?pgbouncer=true (for connection pooling)
```

**Two Connection Modes:**
- `pooler.supabase.com:6543` - Use for APPLICATION (with pgbouncer)
- Direct `aws-1-ap-southeast-1.supabase.com:5432` - Use for migrations/tools

---

## 🛠️ Common Tasks

### Add a New Table

```python
# 1. Create model in backend/db/models.py
class NewTable(BaseModel):
    __tablename__ = "new_table"
    name = Column(String(100), nullable=False)
    
# 2. Create migration
alembic revision --autogenerate -m "Add new_table"

# 3. Apply migration
alembic upgrade head
```

### Query Data

```python
# In backend/api/routes/example.py
from db.database import SessionLocal
from db.models import Branch

db = SessionLocal()
branches = db.query(Branch).all()
db.close()
```

### Raw SQL Query

```python
from sqlalchemy import text
from db.database import SessionLocal

db = SessionLocal()
result = db.execute(text("SELECT * FROM branches WHERE is_active = true"))
db.close()
```

---

## 🔍 Troubleshooting

### Issue: "DATABASE_URL setting is missing"

**Cause:** `.env` file not set or path incorrect

**Solution:**
```bash
# From project root, verify .env exists
ls -la backend/.env

# If missing, create it
cp backend/.env.example backend/.env

# Edit .env with your Supabase credentials
```

### Issue: "could not connect to server: Connection refused"

**Cause:** Database URL is incorrect or Supabase is down

**Solution:**
```bash
# 1. Verify credentials in .env
# 2. Test connection directly
psql "your_database_url"

# 3. Check Supabase status: https://status.supabase.com
```

### Issue: "FATAL: remaining connection slots reserved for non-replication superuser connections"

**Cause:** Too many connections used all available slots

**Solution:**
```python
# In backend/db/database.py, reduce pool_size
pool_kwargs = {
    "pool_size": 5,  # Reduced from 20 for development
    "max_overflow": 2,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
}
```

### Issue: "Alembic revision not found"

**Cause:** Migrations folder corrupted or not initialized

**Solution:**
```bash
# 1. Check migrations exist
ls backend/migrations/versions/

# 2. Re-initialize if needed
cd backend
alembic init migrations -t async

# 3. Re-apply
alembic upgrade head
```

### Issue: "SSL certificate verify failed"

**Cause:** SSL/TLS configuration issue

**Solution:**
Add to `.env`:
```env
DATABASE_URL="postgresql://...?sslmode=require"
```

Or in code:
```python
from sqlalchemy import create_engine, event

engine = create_engine(
    db_url,
    connect_args={"sslmode": "require"}
)
```

---

## 📱 API Endpoints

### Health Check

```bash
GET /api/v1/health
Response: {"status": "healthy", "database": "connected"}
```

### Branches

```bash
GET /api/v1/branches
GET /api/v1/branches/{id}
POST /api/v1/branches
PUT /api/v1/branches/{id}
DELETE /api/v1/branches/{id}
```

### Staff

```bash
GET /api/v1/staff
GET /api/v1/staff/{id}
POST /api/v1/staff
```

### Appointments

```bash
GET /api/v1/appointments
POST /api/v1/appointments
PUT /api/v1/appointments/{id}
```

---

## 🚀 Next Steps

1. **✅ Verify Connection** - Run the verification checklist above
2. **📊 Seed Data** - Optional: `python -m db.seed`
3. **🔌 Test API** - Use curl or Postman to test endpoints
4. **⚛️ Build Frontend** - React components will consume API
5. **🤖 Add Agents** - AI agents use database for context
6. **🚢 Deploy** - Use Docker Compose or Kubernetes

---

## 📚 Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/20/)
- [Alembic Migration Guide](https://alembic.sqlalchemy.org/)
- [FastAPI Database Integration](https://fastapi.tiangolo.com/advanced/sql-databases/)
- [PostgreSQL Connection String](https://www.postgresql.org/docs/current/libpq-connect.html)

---

## ✨ Summary

✅ **Your project is configured for Supabase!**

| Component | Status | Location |
|-----------|--------|----------|
| Database Config | ✅ Ready | `.env` file |
| ORM Setup | ✅ Ready | `backend/db/database.py` |
| Models | ✅ Ready | `backend/db/models.py` |
| Migrations | ✅ Ready | `backend/migrations/` |
| Backend | ✅ Ready | `backend/main.py` |
| Frontend | ✅ Ready | `frontend/src/api/` |

**To get started:**
```bash
cd backend
alembic upgrade head           # Create tables
python -m db.seed             # Seed data (optional)
uvicorn main:app --reload     # Start backend
```

**Then in another terminal:**
```bash
cd frontend
npm run dev                    # Start frontend
```

🎉 **Done! Your application is now connected to Supabase!**
