# SalonAI Workforce - Complete Setup & Configuration Guide

This comprehensive guide will walk you through setting up the SalonAI Workforce project from scratch, including obtaining API keys, configuring environment variables, and running the application.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Overview](#project-overview)
3. [API Keys & External Services](#api-keys--external-services)
4. [Local Development Setup](#local-development-setup)
5. [Docker Setup](#docker-setup)
6. [Environment Configuration](#environment-configuration)
7. [Running the Application](#running-the-application)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)
10. [Common Commands](#common-commands)

---

## Prerequisites

Before starting, ensure you have the following installed on your machine:

### Required Software

1. **Python 3.11+**
   - Download from: https://www.python.org/downloads/
   - Verify installation: `python --version`
   - Required for backend development

2. **Node.js 18+**
   - Download from: https://nodejs.org/
   - Verify installation: `node --version && npm --version`
   - Required for frontend development

3. **Git**
   - Download from: https://git-scm.com/
   - Verify installation: `git --version`
   - Required for cloning and version control

4. **PostgreSQL 15+** (Optional - can use Docker)
   - Download from: https://www.postgresql.org/download/
   - Or use Docker Compose (recommended)
   - Required for database

5. **Docker & Docker Compose** (Recommended)
   - Download Docker Desktop from: https://www.docker.com/products/docker-desktop
   - Includes Docker Compose
   - Simplifies local development environment

### Recommended Editors & Tools

- **VS Code**: https://code.visualstudio.com/
- **Postman** or **Insomnia**: For API testing
- **DBeaver** or **pgAdmin**: For database management (optional)

---

## Project Overview

SalonAI Workforce is a fullstack enterprise application built with:

- **Backend**: FastAPI (Python 3.11) with AI Agents
- **Frontend**: React 18 + TypeScript with Vite
- **Database**: PostgreSQL 15
- **AI**: Microsoft AutoGen for agent orchestration
- **State Management**: Zustand (frontend), SQLAlchemy (backend)
- **Styling**: Tailwind CSS
- **Container Orchestration**: Docker Compose

### Key Features

- Multi-agent AI system for salon workforce management
- RAG (Retrieval Augmented Generation) document processing
- Real-time analytics dashboard
- Appointment booking and management
- Lead tracking and follow-up
- Reputation management tools
- Business intelligence tools

---

## API Keys & External Services

The application integrates with several external services. You need to obtain API keys for these services:

### 1. Groq API Key (LLM Service)

Groq provides fast LLM inference for AI agent operations.

**Steps to obtain:**

1. Visit: https://console.groq.com
2. Sign up for a free account
3. Navigate to "API Keys" section
4. Create a new API key
5. Copy the key and save it safely

**Usage**: The backend uses this for AI agent operations

**Environment Variable**: `GROQ_API_KEY`

### 2. Supabase (Database & Auth - Optional)

Supabase provides PostgreSQL database and authentication services.

**Steps to obtain:**

1. Visit: https://supabase.com
2. Sign up for a free account
3. Create a new project
4. Go to "Project Settings" → "API"
5. Copy your Project URL and anon/public key
6. Note your database password from project setup

**Environment Variables**:
- `SUPABASE_URL`: Your project URL
- `SUPABASE_KEY`: Your anon public key

**Note**: For local development, you can use a local PostgreSQL instance with Docker Compose instead.

---

## Local Development Setup

### Step 1: Clone or Navigate to Project

```bash
# If cloning
git clone <your-repository-url>
cd salon-ai-workforce

# Or navigate to existing project
cd c:\Users\N Balu\Documents\saloon
```

### Step 2: Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# Or on Windows:
copy .env.example .env
```

Edit the `.env` file with your API keys and configuration (see Environment Configuration section below).

### Step 3: Backend Setup

#### On Windows (PowerShell):

```powershell
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get an execution policy error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt

# Return to project root
cd ..
```

#### On macOS/Linux:

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Return to project root
cd ..
```

### Step 4: Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Return to project root
cd ..
```

### Step 5: Database Setup (Local PostgreSQL)

If using local PostgreSQL instead of Docker:

```powershell
# Activate backend virtual environment
cd backend
.\venv\Scripts\Activate.ps1

# Create database (you need PostgreSQL running)
# psql -U postgres -c "CREATE DATABASE salonai_db;"

# Run migrations
alembic upgrade head

cd ..
```

---

## Docker Setup

### Using Docker Compose (Recommended for Development)

Docker Compose handles database, backend, and frontend setup automatically.

#### Prerequisites

- Docker Desktop installed and running

#### Steps

```bash
# Navigate to project root
cd c:\Users\N Balu\Documents\saloon

# Create .env file
copy .env.example .env

# Edit .env with your API keys (see Environment Configuration)

# Start all services
docker-compose up

# Wait for services to start (2-3 minutes)
# You should see messages indicating all services are running
```

#### Access Points

- **Frontend**: http://localhost:5173 or http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **PostgreSQL**: localhost:5432

#### Useful Docker Commands

```bash
# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop all services
docker-compose down

# Remove all volumes (clears database)
docker-compose down -v

# Rebuild containers
docker-compose up --build

# Run migrations in Docker
docker-compose exec backend alembic upgrade head
```

---

## Environment Configuration

### Creating .env File

Create a `.env` file in the project root with the following variables:

```env
# Application Settings
APP_NAME=SalonAI Workforce API
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Database Configuration
# Option 1: Use Docker Compose (recommended)
DATABASE_URL=postgresql://salon_user:salon_password@localhost:5432/salonai_db

# Option 2: Use Supabase
# DATABASE_URL=postgresql://postgres:[PASSWORD]@[PROJECT-ID].supabase.co:5432/postgres

# Database Settings
DATABASE_ECHO=false

# Security
SECRET_KEY=your-super-secret-key-change-in-production
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]

# External Services - REQUIRED
# Groq API Key (free, open-source LLM - get from https://console.groq.com)
GROQ_API_KEY=your-groq-api-key-here

# Supabase (optional - only if using Supabase)
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-anon-public-key-here

# Feature Flags
ENABLE_RAG=true
ENABLE_AGENTS=true

# Frontend Environment Variables
# Create frontend/.env with:
# VITE_API_BASE_URL=http://localhost:8000/api/v1
# VITE_APP_ENV=development
```

### Step-by-Step Configuration

1. **Open .env file** in your text editor
2. **Fill in API Keys**:
   - Replace `your-groq-api-key-here` with your actual Groq API key (free)
   - Add any other external service keys
3. **Set DATABASE_URL**:
   - For Docker Compose: Keep default or match docker-compose.yml
   - For Supabase: Use your Supabase connection string
4. **Configure CORS_ORIGINS** (if needed):
   - Add all frontend URLs that will access the API
   - Format: `["http://localhost:5173", "http://example.com"]`
5. **Set SECRET_KEY**:
   - For production: Use a strong random key
   - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### Frontend Environment Variables

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_ENV=development
```

For production:

```env
VITE_API_BASE_URL=https://your-domain.com/api/v1
VITE_APP_ENV=production
```

### Important Security Notes

- **Never commit .env files** to Git
- **.env is in .gitignore** - Keep it private
- **Store API keys securely** - Use password managers
- **Rotate keys regularly** - For production environments
- **Use different keys** - For development, staging, and production
- **Never share your keys** - Even with team members directly; use secure sharing methods

---

## Running the Application

### Option 1: Using Quick Start Script (Windows)

```powershell
# Navigate to project root
cd c:\Users\N Balu\Documents\saloon

# Run the startup script
.\start.ps1
```

This script automatically:
- Creates Python virtual environment (if needed)
- Installs backend dependencies
- Installs frontend dependencies
- Starts both servers

### Option 2: Manual Backend & Frontend (Development)

#### Terminal 1 - Backend

```powershell
# Navigate to backend
cd c:\Users\N Balu\Documents\saloon\backend

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Backend will be available at http://127.0.0.1:8000
# API docs available at http://127.0.0.1:8000/api/docs
```

#### Terminal 2 - Frontend

```powershell
# Navigate to frontend
cd c:\Users\N Balu\Documents\saloon\frontend

# Start frontend development server
npm run dev

# Frontend will be available at http://localhost:5173
```

### Option 3: Docker Compose (Recommended)

```bash
# From project root
cd c:\Users\N Balu\Documents\saloon

# Ensure .env is configured with API keys
# Then start all services
docker-compose up

# Services will be available at:
# - Frontend: http://localhost:5173
# - Backend: http://localhost:8000
# - API Docs: http://localhost:8000/api/docs
# - Database: localhost:5432
```

### Access Your Application

Once running, access:

1. **Frontend Application**: http://localhost:5173 or http://localhost:3000
2. **Backend API**: http://localhost:8000
3. **API Documentation** (Swagger): http://localhost:8000/api/docs
4. **Alternative API Docs** (ReDoc): http://localhost:8000/api/redoc

### Verify Everything is Working

Check that:
- Frontend loads without errors
- API documentation loads at `/api/docs`
- You can see database models and endpoints
- No connection errors in browser console (F12)
- No errors in terminal outputs

---

## Testing

### Backend Tests

```powershell
# Navigate to backend
cd c:\Users\N Balu\Documents\saloon\backend

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_health.py -v

# Run tests with coverage
pytest tests/ --cov=. -v

# Run tests matching a pattern
pytest -k "test_auth" -v
```

### Frontend Tests

```powershell
# Navigate to frontend
cd c:\Users\N Balu\Documents\saloon\frontend

# Run tests (if test setup exists)
npm test

# Run tests with coverage
npm test -- --coverage
```

### API Testing with Postman/Insomnia

1. **Import API**: Use `http://localhost:8000/api/docs` to explore endpoints
2. **Create Collection**: Set base URL to `http://localhost:8000/api/v1`
3. **Test Endpoints**: Make requests to various endpoints
4. **Set Headers**: Add `Authorization: Bearer <token>` for protected endpoints

---

## Troubleshooting

### Issue: "Python not found" or "python is not recognized"

**Solution**:
- Ensure Python 3.11+ is installed
- Add Python to PATH environment variables
- Restart terminal/PowerShell
- Verify with: `python --version`

### Issue: "Module not found" errors

**Solution**:
```powershell
# Ensure virtual environment is activated
cd backend
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: "npm: command not found"

**Solution**:
- Ensure Node.js 18+ is installed
- Verify with: `npm --version`
- Restart terminal
- Reinstall Node.js if necessary

### Issue: Port already in use (8000 or 5173)

**Solution**:
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use different port
uvicorn main:app --reload --port 8001
```

### Issue: Database connection refused

**Solution**:
- Verify PostgreSQL is running (if not using Docker)
- Check DATABASE_URL in .env file
- For Docker: Ensure Docker Desktop is running
- Run: `docker-compose up -d` to start database container
- Wait 30 seconds for database to be ready

### Issue: GROQ_API_KEY not found error

**Solution**:
- Verify .env file exists in project root
- Check that GROQ_API_KEY is set in .env
- No quotes around the key value
- Reload/restart application
- Verify key format from https://console.groq.com

### Issue: CORS errors in browser console

**Solution**:
- Check CORS_ORIGINS in .env file
- Ensure your frontend URL is in the list
- Format: `["http://localhost:5173", "http://example.com"]`
- Restart backend server
- Clear browser cache

### Issue: Docker container won't start

**Solution**:
```bash
# View detailed logs
docker-compose logs backend
docker-compose logs frontend

# Rebuild containers
docker-compose down -v
docker-compose up --build

# Check Docker is running
docker --version
docker ps
```

### Issue: Frontend can't reach backend API

**Solution**:
- Check VITE_API_BASE_URL in frontend/.env
- Should match backend URL: `http://localhost:8000/api/v1`
- Restart frontend dev server after changing .env
- Clear browser cache
- Check browser console for CORS errors

### Issue: Database migrations fail

**Solution**:
```powershell
# Activate backend environment
cd backend
.\venv\Scripts\Activate.ps1

# Check migration status
alembic current

# Downgrade if needed
alembic downgrade -1

# Upgrade again
alembic upgrade head
```

---

## Common Commands

### Python / Backend Commands

```powershell
# Navigate to backend
cd backend

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Deactivate virtual environment
deactivate

# Install new package and save to requirements
pip install <package_name>
pip freeze > requirements.txt

# Run server in development
uvicorn main:app --reload

# Run server on specific port
uvicorn main:app --reload --port 8001

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_auth.py -v

# Run with coverage
pytest --cov=. tests/

# Format code (if black is installed)
black . --line-length 100

# Lint code (if flake8 is installed)
flake8 . --max-line-length 100
```

### npm / Frontend Commands

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

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage

# Format code (if prettier is installed)
npm run format

# Lint code (if eslint is installed)
npm run lint

# Install new package
npm install <package_name>

# Install dev dependency
npm install -D <package_name>

# Update packages
npm update
```

### Docker Commands

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop all services
docker-compose down

# Remove everything including volumes
docker-compose down -v

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Rebuild images
docker-compose up --build

# Run command in running container
docker-compose exec backend bash
docker-compose exec frontend bash

# Check service status
docker-compose ps
```

### Database Commands

```powershell
# Activate backend environment first
cd backend
.\venv\Scripts\Activate.ps1

# Create new migration
alembic revision --autogenerate -m "Your migration message"

# Apply migrations
alembic upgrade head

# View migration history
alembic history

# Downgrade last migration
alembic downgrade -1

# Drop all tables and recreate
alembic downgrade base
alembic upgrade head
```

### Git Commands

```bash
# Clone repository
git clone <repository_url>

# Create new branch
git checkout -b feature/your-feature-name

# Commit changes
git add .
git commit -m "Your commit message"

# Push to remote
git push origin feature/your-feature-name

# Create pull request (via GitHub web interface)
```

---

## Getting Help

### Resources

1. **FastAPI Docs**: https://fastapi.tiangolo.com/
2. **React Docs**: https://react.dev/
3. **Vite Docs**: https://vitejs.dev/
4. **PostgreSQL Docs**: https://www.postgresql.org/docs/
5. **Docker Docs**: https://docs.docker.com/
6. **Groq Docs**: https://console.groq.com/docs

### Common Issues Resolution

1. **Check logs**: Look at terminal output for error messages
2. **Verify environment**: Ensure .env file has all required variables
3. **Test API**: Use Postman/Insomnia to verify endpoints work
4. **Check database**: Verify database is running and accessible
5. **Review documentation**: Check API docs at http://localhost:8000/api/docs

---

## Next Steps

After setup is complete:

1. ✅ Explore API documentation at http://localhost:8000/api/docs
2. ✅ Test endpoints using Postman or API docs interface
3. ✅ Review frontend application at http://localhost:5173
4. ✅ Check database schema in tools like DBeaver
5. ✅ Read ARCHITECTURE.md for system design details
6. ✅ Review DEVELOPER_GUIDE.md for development patterns
7. ✅ Implement custom features as needed

---

## Support & Feedback

For issues, questions, or feedback:

1. Check this guide first
2. Review API documentation
3. Check browser console for errors (F12)
4. Review terminal/Docker logs
5. Verify all API keys are correctly configured

---

**Last Updated**: May 27, 2026

**Version**: 1.0

