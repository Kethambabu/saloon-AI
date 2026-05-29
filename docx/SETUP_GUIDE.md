# SalonAI Workforce Platform - Supabase Migration & Setup Guide

This guide details the steps to launch, configure, and verify the SalonAI platform migrated to use **Supabase Cloud Database** as its sole database and storage engine.

---

## 1. Prerequisites
- Python 3.10 or higher installed.
- Node.js 18 or higher installed.
- A free Supabase account at [supabase.com](https://supabase.com).
- A free Groq account and API key at [console.groq.com](https://console.groq.com).

---

## 2. Supabase Cloud Database Configuration

### Step A: Initialize the Supabase Project
1. Log in to the [Supabase Console](https://database.supabase.com) and create a **New Project**.
2. Select your preferred region and set a secure database password.
3. Once the database is ready, copy your **Database Connection String** from `Project Settings -> Database -> Connection string -> Session / Transaction Pooler`.
4. Ensure it has the format: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require`.

### Step B: Execute Database Schemas & Seeds
1. Navigate to the **SQL Editor** tab in your Supabase dashboard.
2. Create a new query, open [supabase_init.sql](file:///c:/Users/N%20Balu/Documents/saloon/supabase_init.sql) from the SalonAI project root, copy the contents, paste them into the SQL Editor, and click **Run**.
3. This creates all tables (including role profile tables, chat logs, notifications, and analytics), activates optimized database indexes, configures Row Level Security (RLS) policies, and populates realistic seed data.

### Step C: Storage Buckets Configuration
1. Navigate to the **Storage** tab in your Supabase dashboard.
2. Click **New Bucket** and create the following three buckets:
   - `profile-images` (make it public or authenticated)
   - `documents`
   - `salon-assets`
3. These bucket names map directly to the backend upload routines.

---

## 3. Environment Variables Configuration

In the SalonAI root directory, update your `.env` file with your specific values based on the following template (aligned with [.env.example](file:///c:/Users/N%20Balu/Documents/saloon/.env.example)):

```ini
# Application Settings
APP_NAME="SalonAI Workforce API"
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
LOG_FORMAT=json

# Server Settings
HOST=127.0.0.1
PORT=8000
SECRET_KEY=your-jwt-signing-secret-key-here

# Database Configuration (Supabase Pooled Connection)
DATABASE_URL=postgresql://postgres.your-project-id:your-password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
DATABASE_ECHO=false

# Groq LLM API Key (Free)
GROQ_API_KEY=gsk_your-groq-api-key-here
GROQ_MODEL=llama-3.3-70b-versatile

# Supabase External Services (Required for Storage and Client Actions)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 4. Run the Development Platform

Use the provided PowerShell script in the root directory to automatically launch both the backend and frontend servers in separate terminal windows:

```powershell
.\start.ps1
```

Alternatively, launch them manually:

### Start Backend FastAPI Server
```powershell
cd backend
.\venv\Scripts\activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Start Frontend React Server
```powershell
cd frontend
npm install
npm run dev
```

---

## 5. Roster Login Credentials

You can test each dashboard using the pre-seeded credentials (all passwords are set to `password123`):

1. **👑 Platform Admin Console:**
   - Email: `owner@salonai.com`
   - Password: `password123`
2. **💼 Branch Manager:**
   - Email: `manager@salonai.com`
   - Password: `password123`
3. **💇 Staff / Stylist Dashboard:**
   - Email: `marcus@salonai.com`
   - Password: `password123`
4. **👤 Customer Profile:**
   - Email: `customer@example.com`
   - Password: `password123`
