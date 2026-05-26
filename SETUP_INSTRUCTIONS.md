# SalonAI Workforce - Quick Setup Instructions

This file contains the most essential setup steps to get the development environment running quickly.

## 30-Second Start (Windows)

```powershell
.\start.ps1
```

This will:
1. Create Python virtual environment (if needed)
2. Install all backend dependencies
3. Install all frontend dependencies
4. Start both development servers

Servers will be available at:
- Frontend: http://localhost:5173
- Backend: http://127.0.0.1:8000

## Manual Setup (if needed)

### Backend Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

## Important Commands

### Add Python Package

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install package_name
pip freeze > requirements.txt
```

### Add npm Package

```powershell
cd frontend
npm install package_name
# or dev dependency
npm install -D package_name
```

### Run Tests

**Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

**Frontend:**
```powershell
cd frontend
npm test
```

### Format Code

**Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
black . --line-length 100
```

**Frontend:**
```powershell
cd frontend
npm run format
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Minimum required for development:
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
```

## Troubleshooting

### Port Already in Use

```powershell
# Find process
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F
```

### Clear Python Cache

```powershell
cd backend
rm -r venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Clear npm Cache

```powershell
cd frontend
rm -r node_modules package-lock.json
npm install
```

## Next Steps

1. Read [setup.md](setup.md) for complete documentation
2. Read [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for development standards
3. Check API documentation at http://127.0.0.1:8000/docs

## Quick Links

- **Full Setup Guide:** [setup.md](setup.md)
- **Developer Guide:** [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Project README:** [README.md](README.md)
- **Backend Requirements:** [backend/requirements.txt](backend/requirements.txt)
- **Frontend Config:** [frontend/package.json](frontend/package.json)

---

**Got stuck?** Check the [Troubleshooting section in setup.md](setup.md#troubleshooting)
