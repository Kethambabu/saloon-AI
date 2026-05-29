# 🚀 SalonAI Workforce - Complete Project Runtime Guide

This guide provides detailed step-by-step instructions for running the SalonAI Workforce application locally. This is a full-stack application with a Python FastAPI backend and React TypeScript frontend.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup (One-Time)](#initial-setup-one-time)
3. [Quick Start (5 minutes)](#quick-start-5-minutes)
4. [Running Backend Only](#running-backend-only)
5. [Running Frontend Only](#running-frontend-only)
6. [Running Full Stack](#running-full-stack)
7. [Environment Configuration](#environment-configuration)
8. [Database Setup](#database-setup)
9. [Troubleshooting](#troubleshooting)
10. [Common Commands](#common-commands)

---

## 📦 Prerequisites

### System Requirements
- **Windows 10/11** (this project uses PowerShell scripts)
- **Git** (for version control)
- **Python 3.11+** (verify with `python --version`)
- **Node.js 18+** (verify with `node --version`)
- **npm 9+** (verify with `npm --version`)

### Accounts Required
- **Supabase Account** (for PostgreSQL database)
- **Groq API Key** (free, for LLM/AI agents)
  - Sign up at: https://console.groq.com
  - Generate an API key from your dashboard

### Verify Prerequisites
```powershell
# Check Python
python --version  # Should show 3.11+

# Check Node
node --version    # Should show 18+
npm --version     # Should show 9+

# Check Git
git --version
```

---

## 🔧 Initial Setup (One-Time)

### Step 1: Clone/Open Project

```powershell
cd C:\Users\N Balu\Documents\saloon
```

### Step 2: Run Setup Script

The easiest way to set up everything is to use the provided setup script:

```powershell
# Option A: Using the automatic setup script
.\setup.bat

# Option B: Manual setup (see below)
```

### Step 3: Manual Setup (if setup.bat doesn't work)

#### 3a. Create and Activate Python Virtual Environment

```powershell
# Navigate to project root
cd C:\Users\N Balu\Documents\saloon

# Create virtual environment
python -m venv .venv

# Activate it (PowerShell)
.venv\Scripts\Activate.ps1

# If you get an execution policy error, run this first:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

#### 3b. Install Backend Dependencies

```powershell
# From project root with venv activated
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Verify critical packages
pip list | findstr "fastapi sqlalchemy asyncpg langchain-groq"
```

#### 3c. Install Frontend Dependencies

```powershell
# From project root (different terminal or after backend is done)
cd frontend

# Install Node dependencies
npm install

# Verify installation
npm list react vite typescript
```

### Step 4: Environment Configuration

```powershell
# Copy the environment template to .env file
cd backend

# Create .env from template (or copy manually)
Copy-Item "..\backend\.env" -Destination ".env" -Force
# Edit .env with your values (see section below)
```

See [Environment Configuration](#environment-configuration) section for details.

### Step 5: Database Setup

```powershell
# From backend directory with venv activated
cd backend

# Initialize database (creates tables and seeds data)
python init_db.py

# Or manually run migrations
alembic upgrade head

# Seed sample data
python -m db.seed

# Verify connection
python ..\verify_supabase.py
```

---

## ⚡ Quick Start (5 minutes)

Once you've completed Initial Setup, here's the fastest way to start developing:

### Terminal 1: Backend
```powershell
cd C:\Users\N Balu\Documents\saloon
.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Terminal 2: Frontend
```powershell
cd C:\Users\N Balu\Documents\saloon
cd frontend
npm run dev
```

**Expected output:**
```
  VITE v5.2.0  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Open in Browser
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

---

## 🔙 Running Backend Only

### Step 1: Activate Virtual Environment

```powershell
cd C:\Users\N Balu\Documents\saloon

# First time setup
python -m venv .venv

# Activate (PowerShell)
.venv\Scripts\Activate.ps1

# If execution policy error:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Step 2: Navigate to Backend

```powershell
cd backend
```

### Step 3: Start Development Server

```powershell
# Basic start
uvicorn main:app --reload

# With custom host/port
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# With detailed logging
uvicorn main:app --reload --log-level debug
```

### Step 4: Access Backend

- **API Base URL**: `http://localhost:8000`
- **Interactive API Docs**: `http://localhost:8000/docs`
- **ReDoc API Docs**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

### Run Backend Tests

```powershell
# In backend directory with venv activated
pytest

# Run specific test file
pytest tests/test_health.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=api --cov=agents --cov=db

# Run specific test class/function
pytest tests/test_api_endpoints.py::TestHealthEndpoint::test_health_check
```

### Stop Backend Server

Press `Ctrl+C` in the terminal running uvicorn.

---

## 🎨 Running Frontend Only

### Step 1: Navigate to Frontend

```powershell
cd C:\Users\N Balu\Documents\saloon\frontend
```

### Step 2: Install Dependencies (first time only)

```powershell
npm install
```

### Step 3: Start Development Server

```powershell
# Basic development server
npm run dev

# Preview production build
npm run preview
```

### Step 4: Access Frontend

- **Development Server**: `http://localhost:5173`
- **Production Preview**: `http://localhost:4173`

### Frontend Development Commands

```powershell
# Type checking
npm run type-check

# Linting
npm run lint

# Fix linting issues
npm run lint:fix

# Code formatting
npm run format

# Check formatting without applying
npm run format:check

# Build for production
npm run build

# Preview production build locally
npm run preview
```

### Stop Frontend Server

Press `Ctrl+C` in the terminal running npm dev.

---

## 🔄 Running Full Stack

The recommended way is to run backend and frontend in separate terminals:

### Method 1: Two Terminal Windows (Recommended)

**Terminal 1 - Backend:**
```powershell
cd C:\Users\N Balu\Documents\saloon
.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd C:\Users\N Balu\Documents\saloon
cd frontend
npm run dev
```

Then visit: http://localhost:5173

### Method 2: Using PowerShell Script

```powershell
# From project root
.\start.ps1

# Or specify which to start
.\start.ps1 -Backend      # Backend only
.\start.ps1 -Frontend     # Frontend only
.\start.ps1 -Both         # Both (default)
```

### Method 3: Using Batch Scripts

```powershell
# Run backend
.\run_backend.bat

# Run frontend (in different terminal)
.\run_frontend.bat
```

### Verify Full Stack is Running

1. **Backend Health Check:**
   ```powershell
   curl http://localhost:8000/health
   # Should return: {"status":"healthy"}
   ```

2. **Frontend Access:**
   - Open http://localhost:5173 in browser

3. **API Documentation:**
   - Open http://localhost:8000/docs in browser

4. **Test API Connection:**
   ```powershell
   curl http://localhost:8000/api/branches
   # Should return list of branches
   ```

---

## 🔐 Environment Configuration

### Step 1: Get Required Credentials

#### Supabase (PostgreSQL Database)
1. Go to https://supabase.com
2. Create a new project
3. Get your credentials:
   - Project URL
   - Anon Key
   - Service Role Key
   - Database Password
   - Database URL (Connection String)

#### Groq API Key (LLM Provider)
1. Go to https://console.groq.com
2. Create API key
3. Copy the key

### Step 2: Create .env File

Copy the template and fill in values:

```powershell
cd C:\Users\N Balu\Documents\saloon\backend

# Create .env file from existing template
```

### Step 3: Edit .env File

Open `backend\.env` in VS Code and fill in:

```env
# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
APP_NAME="SalonAI Workforce API"
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# ============================================================================
# SERVER SETTINGS
# ============================================================================
HOST=0.0.0.0
PORT=8000
SECRET_KEY=your-super-secret-key-change-in-production

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173"]

# ============================================================================
# DATABASE CONFIGURATION (Supabase)
# ============================================================================
# Format: postgresql://user:password@host:port/database
# Get from Supabase project settings
DATABASE_URL=postgresql://postgres:your-password@db.xxx.supabase.co:5432/postgres

# ============================================================================
# SUPABASE CREDENTIALS
# ============================================================================
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# ============================================================================
# LLM CONFIGURATION (Groq)
# ============================================================================
# Get from https://console.groq.com/keys
GROQ_API_KEY=your-groq-api-key

# Available models (Jan 2025):
# - llama-3.3-70b-versatile (recommended, most capable)
# - llama-3.1-8b-instant (fast, fallback)
# - mixtral-8x7b-32768
# - gemma-7b-it
LLM_MODEL_PRIMARY=llama-3.3-70b-versatile
LLM_MODEL_FALLBACK=llama-3.1-8b-instant
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# ============================================================================
# JWT AUTHENTICATION
# ============================================================================
JWT_SECRET_KEY=your-jwt-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# ============================================================================
# RAG/EMBEDDINGS CONFIGURATION
# ============================================================================
# Using HuggingFace embeddings (local, no API key needed)
EMBEDDINGS_MODEL=all-MiniLM-L6-v2
VECTOR_DIMENSION=384

# ============================================================================
# EMAIL CONFIGURATION (optional)
# ============================================================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=noreply@salonai.local

# ============================================================================
# MONITORING & LOGGING
# ============================================================================
LOG_FORMAT=json
LOG_LEVEL=INFO
SENTRY_DSN=  # Optional: for error tracking

# ============================================================================
# FEATURE FLAGS
# ============================================================================
ENABLE_RAG=true
ENABLE_AGENTS=true
ENABLE_BACKGROUND_TASKS=true
```

### Step 4: Validate Configuration

```powershell
# From backend directory
python -c "from core.config import get_settings; s = get_settings(); print('✅ Config loaded successfully')"
```

---

## 🗄️ Database Setup

### Initial Database Creation

```powershell
cd C:\Users\N Balu\Documents\saloon\backend

# Activate venv
.venv\Scripts\Activate.ps1

# Option 1: Automatic (recommended)
python init_db.py

# Option 2: Manual migrations
alembic upgrade head

# Option 3: Create fresh schema
python -c "from db.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Seed Sample Data

```powershell
# From backend directory
python -m db.seed

# Verify data was inserted
python
```

Then in Python REPL:

```python
from db.database import SessionLocal
from db.models import Branch, Staff, Service

session = SessionLocal()
print(f"Branches: {session.query(Branch).count()}")
print(f"Staff: {session.query(Staff).count()}")
print(f"Services: {session.query(Service).count()}")
session.close()
```

### Database Commands

```powershell
# View database connection
python -c "from db.database import check_db_health; print('DB Health:', check_db_health())"

# Run migrations
alembic upgrade head

# View migration history
alembic current

# Create new migration (after model changes)
alembic revision --autogenerate -m "Add new column"

# Rollback last migration
alembic downgrade -1

# Reset database (CAREFUL!)
alembic downgrade base
alembic upgrade head
```

### Access Supabase Console

1. Go to https://supabase.com
2. Log in to your project
3. Click "SQL Editor"
4. View tables, run queries directly

---

## 🐛 Troubleshooting

### Backend Issues

#### Issue: "ModuleNotFoundError: No module named 'fastapi'"

**Solution:**
```powershell
# Ensure venv is activated
.venv\Scripts\Activate.ps1

# Reinstall requirements
cd backend
pip install -r requirements.txt --force-reinstall

# Verify
python -c "import fastapi; print(fastapi.__version__)"
```

#### Issue: "ExecutionPolicy is set to Restricted"

**Solution:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

#### Issue: "Unable to connect to database"

**Solution:**
```powershell
# Check DATABASE_URL in .env
cat .env | findstr DATABASE_URL

# Test connection
python -c "from db.database import check_db_health; print(check_db_health())"

# Verify Supabase:
# 1. Is it running?
# 2. Is password correct?
# 3. Is special character URL-encoded? (@=%40)
```

#### Issue: "Groq API Error: Model not found"

**Solution:**
```powershell
# Check your .env
cat .env | findstr LLM_MODEL

# Valid models as of Jan 2025:
# - llama-3.3-70b-versatile (recommended)
# - llama-3.1-8b-instant
# - mixtral-8x7b-32768

# Verify Groq API key works
python -c "from core.llm_config import validate_llm_startup; validate_llm_startup()"
```

#### Issue: "Port 8000 is already in use"

**Solution:**
```powershell
# Find and kill process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use different port
uvicorn main:app --reload --port 8001
```

### Frontend Issues

#### Issue: "npm ERR! code ERESOLVE"

**Solution:**
```powershell
cd frontend

# Clear cache
npm cache clean --force

# Reinstall
npm install --legacy-peer-deps
```

#### Issue: "Port 5173 is already in use"

**Solution:**
```powershell
# Kill process
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Or run on different port
npm run dev -- --port 5174
```

#### Issue: "CORS error when calling backend"

**Solution:**
```powershell
# Check CORS_ORIGINS in backend/.env
cat backend\.env | findstr CORS

# Should include frontend URL:
CORS_ORIGINS=["http://localhost:5173"]

# Restart backend after changing
```

#### Issue: "TypeScript errors in IDE"

**Solution:**
```powershell
cd frontend

# Run type check
npm run type-check

# Fix issues
npm run lint:fix

# Reload VS Code
```

### General Issues

#### Issue: "Python version mismatch"

**Solution:**
```powershell
# Check Python version
python --version  # Should be 3.11+

# If you have multiple versions:
python3.11 --version
python3.11 -m venv .venv
```

#### Issue: "Git merge conflicts"

**Solution:**
```powershell
# Stash changes
git stash

# Pull latest
git pull origin main

# Apply stashed changes
git stash pop
```

---

## 📚 Common Commands

### Backend Commands

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Navigate to backend
cd backend

# Start development server
uvicorn main:app --reload

# Run tests
pytest

# Run specific test
pytest tests/test_health.py -v

# Check code quality
# (if pre-commit hooks are set up)
pre-commit run --all-files

# Format code
black .

# Check imports
isort --check-only .

# Fix imports
isort .
```

### Frontend Commands

```powershell
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run type-check

# Linting
npm run lint
npm run lint:fix

# Code formatting
npm run format
npm run format:check
```

### Database Commands

```powershell
# Activate venv first
.venv\Scripts\Activate.ps1
cd backend

# Initialize database
python init_db.py

# Seed sample data
python -m db.seed

# Run migrations
alembic upgrade head

# Check migration status
alembic current

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback migration
alembic downgrade -1

# Verify Supabase connection
python ..\verify_supabase.py
```

### Project Management

```powershell
# Check Git status
git status

# View recent commits
git log --oneline -10

# Create new branch
git checkout -b feature/my-feature

# Switch branch
git checkout main

# Pull latest
git pull origin main

# Push changes
git push origin feature/my-feature
```

---

## 📊 Project Architecture

```
saloon/
├── backend/                    # FastAPI application
│   ├── main.py                # Entry point
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Configuration (gitignored)
│   ├── core/                  # Core utilities
│   │   ├── config.py          # Settings management
│   │   ├── llm_config.py      # LLM configuration
│   │   └── security.py        # Auth utilities
│   ├── db/                    # Database layer
│   │   ├── database.py        # Connection pooling
│   │   ├── models.py          # SQLAlchemy models
│   │   └── seed.py            # Sample data
│   ├── agents/                # AI agents
│   │   ├── receptionist_agent.py
│   │   ├── bi_agent.py
│   │   └── orchestrator.py
│   ├── api/                   # REST API
│   │   ├── main.py
│   │   └── routes/            # Endpoint routes
│   ├── tests/                 # Test suite
│   └── rag/                   # RAG system
│
├── frontend/                   # React application
│   ├── src/
│   │   ├── main.tsx           # Entry point
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── hooks/             # Custom hooks
│   │   ├── store/             # Zustand state
│   │   └── api/               # API client
│   ├── package.json           # Node dependencies
│   ├── vite.config.ts         # Vite configuration
│   └── tsconfig.json          # TypeScript config
│
├── .env                        # Project env (root level, optional)
├── .venv/                      # Python virtual environment
├── alembic.ini                # Database migration config
├── setup.bat                  # Windows setup script
├── start.ps1                  # Start script
└── HOW_TO_RUN_PROJECT.md     # This file
```

---

## 🎯 Next Steps After Running

1. **Access the frontend**: http://localhost:5173
2. **Explore API docs**: http://localhost:8000/docs
3. **Run tests**: `pytest` in backend directory
4. **Check database**: View tables in Supabase console
5. **Try agents**: Call agent endpoints via Swagger UI
6. **Read documentation**: Check `docx/` folder for detailed docs

---

## 📞 Quick Reference

| Component | Port | URL | Purpose |
|-----------|------|-----|---------|
| Frontend | 5173 | http://localhost:5173 | React UI |
| Backend API | 8000 | http://localhost:8000 | FastAPI server |
| API Docs | 8000 | http://localhost:8000/docs | Swagger UI |
| ReDoc Docs | 8000 | http://localhost:8000/redoc | ReDoc UI |

---

## 🔒 Important Notes

1. **Never commit .env files** - They contain secrets
2. **Use .env.example** - As template for others
3. **Keep dependencies updated** - Run `pip install -r requirements.txt --upgrade` periodically
4. **Run tests before pushing** - Use `pytest` to catch issues early
5. **Clear cache if issues occur** - `npm cache clean --force` or `pip cache purge`

---

## ✅ Health Checks

After starting everything, verify it's working:

```powershell
# Backend health
curl http://localhost:8000/health

# Frontend is accessible
Start-Process http://localhost:5173

# Database is connected
python -c "from db.database import check_db_health; print(check_db_health())"

# LLM is configured
python -c "from core.llm_config import validate_llm_startup; print(validate_llm_startup())"
```

---

## 📖 More Documentation

For more detailed information, see:

- `docx/QUICKSTART.md` - 5-minute quick start
- `docx/ARCHITECTURE.md` - System architecture
- `docx/DEPLOYMENT.md` - Production deployment
- `docx/LLM_CONFIGURATION_GUIDE.md` - LLM setup details
- `docx/SUPABASE_SETUP_GUIDE.md` - Database setup
- `backend/README.md` - Backend specifics
- `frontend/README.md` - Frontend specifics

---

**Last Updated**: May 29, 2026
**Status**: ✅ Ready for Production
**Version**: 1.0
