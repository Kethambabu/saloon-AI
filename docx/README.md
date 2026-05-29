# SalonAI Workforce Platform - Windows-Native Local Setup

SalonAI is a production-grade, multi-agent enterprise hub designed for salon workforce orchestration. It integrates a **FastAPI backend** (running in a local Python virtual environment), a **React/Vite frontend** (running in Node.js), and a **Supabase Cloud Database** as its sole data and storage layer.

**This project has been completely optimized for Windows-native local execution.**
- ❌ **NO Docker Desktop required.**
- ❌ **NO WSL / Linux dependencies.**
- ❌ **NO Local PostgreSQL installation required.**

---

## 1. System Prerequisites

Before starting, ensure your Windows machine has the following tools installed:
1. **Python 3.10+**: Download and install from [python.org](https://www.python.org/downloads/).
   - *Important:* Check the box **"Add Python to PATH"** during installation.
2. **Node.js 18+**: Download and install from [nodejs.org](https://nodejs.org/).
   - *Important:* Ensure `npm` is added to your environment variables PATH.
3. **Supabase Account**: Register a free cloud database at [supabase.com](https://supabase.com).

---

## 2. Platform Architecture

```
                 +-----------------------------------------+
                 |            React/Vite Frontend          |
                 |          (natively run via npm)         |
                 +-----------------------------------------+
                                      │
                                      ▼ [HTTP / REST RESTful calls]
                 +-----------------------------------------+
                 |            FastAPI Backend              |
                 |          (local Python venv)            |
                 +-----------------------------------------+
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
      +─────────────────────────+           +─────────────────────────+
      |  Supabase Database URL  |           |     Supabase Storage    |
      |   (PostgreSQL Cloud)    |           |   (profile-images bucket)
      +─────────────────────────+           +─────────────────────────+
```

---

## 3. Quick Start Guide (Windows One-Click)

We provide optimized Windows Batch automation scripts (`.bat`) in the root directory to make setup and execution effortless.

### Step 1: Initialize Project dependencies
Double-click [setup.bat](file:///c:/Users/N%20Balu/Documents/saloon/setup.bat) in your root directory, or execute it in your terminal:
```cmd
setup.bat
```
This automatically:
- Verifies system Python and Node.js path settings.
- Creates a Python virtual environment (`venv`) inside the `backend` folder.
- Installs all Python dependencies from `requirements.txt`.
- Installs all React package dependencies in the `frontend` folder.
- Creates your local `.env` configuration file from `.env.example`.

### Step 2: Configure Supabase credentials
Open the newly created `.env` file in the root directory and update it with your Supabase credentials:
```ini
# Supabase pooled database connection string
DATABASE_URL=postgresql://postgres.[project-id]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require

# External Supabase keys
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### Step 3: Initialize Supabase DB tables & seed
1. Log in to your [Supabase Console](https://database.supabase.com) and navigate to the **SQL Editor** tab.
2. Click **New Query**, copy the contents of the [supabase_init.sql](file:///c:/Users/N%20Balu/Documents/saloon/supabase_init.sql) file located in the project root, paste it into the editor, and click **Run**.
3. *Note:* Make sure to also create three storage buckets (`profile-images`, `documents`, `salon-assets`) in your Supabase **Storage** tab!

### Step 4: Run the servers
Once the database is set up and `.env` is configured, you can launch the servers:
- **To Start Backend FastAPI Server:** Double-click [run_backend.bat](file:///c:/Users/N%20Balu/Documents/saloon/run_backend.bat) or run `run_backend.bat`.
- **To Start Frontend Vite Server:** Double-click [run_frontend.bat](file:///c:/Users/N%20Balu/Documents/saloon/run_frontend.bat) or run `run_frontend.bat`.

---

## 4. Test Roster login credentials

The database seeding query automatically registers the following testing credentials (all passwords are set to `password123`):

- 👑 **Admin Console:** `owner@salonai.com`
- 💼 **Branch Manager Dashboard:** `manager@salonai.com`
- 💇 **Staff Stylist workspace:** `marcus@salonai.com`
- 👤 **Salon Customer:** `customer@example.com`

---

## 5. Development Utilities

- **install_requirements.bat**: Run this script to update/reinstall all backend Python packages and frontend Node modules.
- **start.ps1**: A native PowerShell script that starts both backend and frontend servers concurrently.
