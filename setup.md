# SalonAI Workforce - Enterprise Developer Setup Guide

Complete setup instructions for the SalonAI Workforce development environment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Development Environment](#development-environment)
6. [Running the Application](#running-the-application)
7. [Dependency Management](#dependency-management)
8. [IDE Configuration](#ide-configuration)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python:** 3.11 or higher
- **Node.js:** 18 or higher
- **npm:** 9 or higher
- **Git:** Latest version
- **VS Code:** Latest version (recommended)

### Required VS Code Extensions

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)

## Quick Start

### Automatic Setup (Recommended)

```powershell
# From the root directory, run the startup script
.\start.ps1

# This will:
# 1. Create Python virtual environment (if needed)
# 2. Install backend dependencies
# 3. Install frontend dependencies
# 4. Start both development servers in separate windows
```

### Manual Setup

Follow the detailed sections below for manual setup.

## Backend Setup

### Step 1: Create Virtual Environment

```powershell
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (macOS/Linux)
source venv/bin/activate
```

### Step 2: Install Dependencies

```powershell
# Ensure venv is activated
pip install -r requirements.txt
```

### Step 3: Environment Variables

```powershell
# Copy the example .env file
cp .env.example .env

# Edit .env with your configuration
# Important variables to configure:
# - DATABASE_URL: PostgreSQL connection string
# - OPENAI_API_KEY: OpenAI API key
# - SUPABASE_URL and SUPABASE_KEY: Supabase credentials
```

### Step 4: Verify Installation

```powershell
# Test that all dependencies are installed
python -c "import fastapi; import sqlalchemy; print('✓ Backend dependencies OK')"
```

## Frontend Setup

### Step 1: Install Dependencies

```powershell
cd frontend
npm install
```

### Step 2: Verify Installation

```powershell
npm run type-check
npm run lint
```

### Step 3: Build Test

```powershell
npm run build
```

## Development Environment

### VS Code Configuration

The workspace includes `.vscode/settings.json` with:

- **Auto-formatting:** Enabled for Python, TypeScript, and JSON
- **Linting:** ESLint for frontend, Pylint for backend
- **Code formatting:** Black for Python, Prettier for frontend
- **Editor settings:** Rulers at 80 and 100 characters

### Python Environment Configuration

**Location:** `.vscode/settings.json`

```json
"python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
"python.linting.pylintEnabled": true,
"python.formatting.provider": "black"
```

### Git Configuration

A comprehensive `.gitignore` is included to prevent:

- Virtual environment files
- Node modules
- Build artifacts
- Environment variable files (.env)
- IDE settings
- Cache and temporary files

## Running the Application

### Option 1: Using the Startup Script

```powershell
# Start both frontend and backend servers
.\start.ps1

# Start only frontend
.\start.ps1 -Frontend

# Start only backend
.\start.ps1 -Backend
```

### Option 2: Manual Startup

#### Terminal 1 - Backend Server

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

#### Terminal 2 - Frontend Development Server

```powershell
cd frontend
npm run dev
```

### Access URLs

- **Frontend:** http://localhost:5173
- **Backend API:** http://127.0.0.1:8000
- **API Documentation:** http://127.0.0.1:8000/docs

## Dependency Management

### Adding Python Packages

**CRITICAL:** Always update `requirements.txt` after installing new packages.

```powershell
cd backend
.\venv\Scripts\Activate.ps1

# Install new package
pip install <package_name>

# Update requirements.txt
pip freeze > requirements.txt

# Commit both the package installation and requirements.txt update
```

### Adding Node/npm Packages

```powershell
cd frontend

# Install regular dependency
npm install <package_name>

# Install dev dependency
npm install -D <package_name>

# The package-lock.json will be automatically updated
```

### Current Backend Dependencies

```
fastapi==0.104.1              # Web framework
uvicorn==0.24.0               # ASGI server
pyautogen==0.2.0              # Agent framework
sqlalchemy==2.0.23            # ORM
alembic==1.12.1               # Database migrations
langchain==0.1.0              # LLM integration
langchain-openai==0.0.7       # OpenAI integration
faiss-cpu==1.7.4              # Vector search
psycopg2-binary==2.9.9        # PostgreSQL driver
python-dotenv==1.0.0          # Environment variables
pydantic==2.5.0               # Data validation
pytest==7.4.3                 # Testing framework
httpx==0.25.1                 # HTTP client
supabase==2.3.5               # Supabase client
pytest-asyncio==0.21.1        # Async testing
pydantic-settings==2.1.0      # Settings management
```

### Current Frontend Dependencies

**Runtime:**
- react@^18.2.0
- react-dom@^18.2.0

**Development:**
- @vitejs/plugin-react@^4.2.1
- typescript@^5.2.2
- tailwindcss@^3.4.3
- eslint@^8.57.0
- prettier@^3.1.1
- And related type definitions

## IDE Configuration

### Recommended VSCode Settings

**Auto-format on save:** Already configured in `.vscode/settings.json`

### Python Linting

Configurations in `backend/pyproject.toml`:

- **Black:** Line length 100, Python 3.11+
- **isort:** Import sorting with Black compatibility
- **Pylint:** Code quality checks
- **MyPy:** Type checking

### Frontend Linting

Configurations:

- **ESLint:** `frontend/eslint.config.js`
- **Prettier:** `frontend/.prettierrc`
- **TypeScript:** Strict type checking enabled

### Running Linters

**Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pylint core/ main.py
```

**Frontend:**
```powershell
cd frontend
npm run lint
npm run lint:fix        # Auto-fix issues
npm run format          # Format code with Prettier
```

## Testing

### Backend Tests

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/ -v
pytest tests/ --cov=core  # With coverage
```

### Frontend Tests

```powershell
cd frontend
npm test
```

## Environment Variables

### Development Environment

Copy `.env.example` to `.env` and configure:

```env
# Application
APP_NAME=SalonAI Workforce
ENVIRONMENT=development
DEBUG=true

# Server
SERVER_HOST=127.0.0.1
SERVER_PORT=8000

# Database (Optional - will use in-memory if not set)
DATABASE_URL=postgresql://user:password@localhost:5432/salonai

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# API Keys (Get from services)
OPENAI_API_KEY=your-key-here
SUPABASE_URL=your-url-here
SUPABASE_KEY=your-key-here
```

## Troubleshooting

### Python Virtual Environment Issues

```powershell
# Recreate virtual environment
rm -r backend/venv
python -m venv backend/venv
.\backend\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### Node Modules Issues

```powershell
# Clear npm cache and reinstall
cd frontend
rm -r node_modules package-lock.json
npm install
```

### Port Already in Use

```powershell
# Find process using port
netstat -ano | findstr :8000    # Backend
netstat -ano | findstr :5173    # Frontend

# Kill process
taskkill /PID <PID> /F
```

### Python Import Errors

```powershell
# Verify virtual environment is activated
# The prompt should show (venv) prefix

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### ESLint/Prettier Errors

```powershell
cd frontend
npm run lint:fix
npm run format
```

## Development Workflow

### Before Starting Development

1. Activate Python virtual environment: `.\backend\venv\Scripts\Activate.ps1`
2. Copy `.env.example` to `.env` and configure
3. Start development servers: `.\start.ps1`
4. Open http://localhost:5173 in browser

### Committing Code

1. Run linters: `npm run lint` (frontend), `pylint` (backend)
2. Fix formatting: `npm run format` (frontend)
3. Run tests: `pytest` (backend), `npm test` (frontend)
4. Commit changes with clear messages

### Adding Dependencies

1. Install package: `pip install <pkg>` or `npm install <pkg>`
2. Update `requirements.txt`: `pip freeze > requirements.txt` (Python only)
3. Test the installation
4. Commit `requirements.txt` changes immediately

## Documentation

- **Backend API Docs:** http://127.0.0.1:8000/docs (FastAPI Swagger UI)
- **Backend Alternative Docs:** http://127.0.0.1:8000/redoc (ReDoc)
- **Frontend Documentation:** See `frontend/README.md`

## Getting Help

- Check logs in the terminal windows
- Review error messages carefully
- Consult the Troubleshooting section
- Check relevant configuration files:
  - Backend: `backend/core/config.py`, `backend/pyproject.toml`
  - Frontend: `frontend/package.json`, `frontend/eslint.config.js`

---

**Last Updated:** May 24, 2026
**Project:** SalonAI Workforce
**Version:** 0.1.0
