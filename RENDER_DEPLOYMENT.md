# Deploying SalonAI to Render (Frontend & Backend via Docker)

This guide walks you through deploying the **SalonAI Workforce Platform** (FastAPI Backend + React/Nginx Frontend) to [Render](https://render.com) using Docker.

---

## Architecture Overview

* **Backend Service (`backend/Dockerfile`)**:
  * **Image**: Python 3.11 Slim
  * **Framework**: FastAPI + Uvicorn
  * **Dynamic Port**: Listens on the `$PORT` assigned dynamically by Render.
  * **Health Check**: `/health` endpoint.
* **Frontend Service (`frontend/Dockerfile`)**:
  * **Multi-stage Build**: Node 20 builder compiles React + Vite, served by lightweight Nginx Alpine.
  * **Dynamic Port**: Nginx template automatically substitutes Render's dynamic `$PORT`.
  * **Client Routing**: Full SPA fallback support (`try_files $uri $uri/ /index.html`).
  * **Health Check**: `/health` endpoint.

---

## Option 1: 1-Click Blueprint Deployment (Recommended)

Render provides Infrastructure-as-Code via `render.yaml` included in this repository.

1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Blueprint**.
3. Connect your GitHub repository: `https://github.com/Kethambabu/saloon-AI.git`.
4. Render will read `render.yaml` and configure both `salonai-backend` and `salonai-frontend`.
5. Enter the required environment variables:
   * **`DATABASE_URL`**: Your PostgreSQL connection string (Supabase or Render PostgreSQL).
   * **`GROQ_API_KEY`**: Your Groq API key for LLM agents.
   * **`CORS_ORIGINS`**: The Render frontend URL (e.g., `https://salonai-frontend.onrender.com`).
   * **`VITE_API_URL`**: The Render backend API endpoint (e.g., `https://salonai-backend.onrender.com/api/v1`).
6. Click **Apply**. Render will build and deploy both containers automatically!

---

## Option 2: Manual Web Service Deployment

If you prefer to configure the services manually in Render:

### Step 1: Deploy Backend

1. In Render, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   * **Name**: `salonai-backend`
   * **Region**: Oregon (or your preferred region)
   * **Runtime**: `Docker`
   * **Docker Context**: `./backend`
   * **Dockerfile Path**: `./backend/Dockerfile`
   * **Health Check Path**: `/health`
4. Add Environment Variables under **Environment**:
   * `ENVIRONMENT`: `production`
   * `LOW_MEMORY_MODE`: `true` *(Keeps memory under 120MB, preventing 512MB OOM)*
   * `SECRET_KEY`: *(Click "Generate" or provide a secure 32+ character random string)*
   * `DATABASE_URL`: Your Supabase connection string (e.g. `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres` or Supabase pooler `6543`)
   * `CORS_ORIGINS`: `https://salonai-frontend.onrender.com,http://localhost:5173`
   * `GROQ_API_KEY`: `your-groq-api-key`
   * `OPENAI_API_KEY`: `your-openai-api-key` *(optional)*
   * `GEMINI_API_KEY`: `your-gemini-api-key` *(optional, enables zero-memory Gemini embeddings)*
5. Click **Create Web Service**. Note the deployed URL (e.g. `https://salonai-backend.onrender.com`).

### Step 2: Deploy Frontend

1. In Render, click **New +** > **Web Service**.
2. Connect the same repository.
3. Configure settings:
   * **Name**: `salonai-frontend`
   * **Region**: Same region as backend
   * **Runtime**: `Docker`
   * **Docker Context**: `./frontend`
   * **Dockerfile Path**: `./frontend/Dockerfile`
   * **Health Check Path**: `/health`
4. Expand **Advanced** > **Docker Build Arguments**:
   * `VITE_API_URL`: `https://salonai-backend.onrender.com/api/v1`
5. Click **Create Web Service**.

> **Note**: If you update the backend URL later, trigger a manual deploy with cache clear on the frontend so Vite bakes the new `VITE_API_URL` into the static bundle.

---

## Local Verification with Docker Compose

Before pushing to production, you can test the entire containerized stack locally:

```bash
# Build and run backend + frontend together
docker compose up --build

# Backend will be available at: http://localhost:8000
# Frontend will be available at: http://localhost:3000
```

---

## Troubleshooting Common Render Issues

### 1. `Out of memory (used over 512Mi)`
* **Cause**: Heavy local PyTorch embedding models exceed Render's 512MB RAM free/starter limit.
* **Fix**: The codebase automatically enables `LightweightEmbeddings` in Render environments (`LOW_MEMORY_MODE=true`). This drops memory usage from ~650MB down to ~95MB, well below Render's limit.
* **Optional**: Provide `GEMINI_API_KEY` to use Google's cloud embeddings (also 0MB RAM).

### 2. `Supabase connection failed: No module named 'psycopg'`
* **Cause**: Supabase connection strings use `postgresql://` which expects `psycopg` (v3) or `psycopg2`.
* **Fix**: Both `psycopg[binary]` and `psycopg2-binary` are installed, with automatic dialect normalization in `infrastructure/db/database.py`. You can supply connection strings starting with either `postgresql://` or `postgresql+psycopg2://`.

### 3. `No open ports detected, continuing to scan...`
* **Cause**: Blocking tasks during startup delayed Uvicorn from binding to Render's dynamic `$PORT`.
* **Fix**: Embeddings are now lazy-loaded on first use, allowing Uvicorn to bind to `$PORT` in under 2 seconds.
