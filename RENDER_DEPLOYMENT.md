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
   * `SECRET_KEY`: *(Click "Generate" or provide a secure 32+ character random string)*
   * `DATABASE_URL`: `postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres`
   * `CORS_ORIGINS`: `https://salonai-frontend.onrender.com,http://localhost:5173`
   * `GROQ_API_KEY`: `your-groq-api-key`
   * `OPENAI_API_KEY`: `your-openai-api-key` *(optional)*
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
