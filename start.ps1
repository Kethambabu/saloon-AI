# start.ps1
# Startup script for SalonAI Workforce Development Environment
# This script initializes and starts both frontend and backend development servers

param(
    [switch]$Frontend = $false,
    [switch]$Backend = $false,
    [switch]$Both = $false
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$message)
    Write-Host "`n================================" -ForegroundColor Cyan
    Write-Host $message -ForegroundColor Cyan
    Write-Host "================================`n" -ForegroundColor Cyan
}

function Test-PathExists {
    param([string]$path)
    if (-not (Test-Path $path)) {
        Write-Host "ERROR: $path not found!" -ForegroundColor Red
        exit 1
    }
}

# If no flags specified, start both
if (-not $Frontend -and -not $Backend) {
    $Both = $true
}

Write-Header "SalonAI Workforce Development Environment"

# Validate required paths
Test-PathExists "frontend"
Test-PathExists "backend"
Test-PathExists ".env.example"

# Backend setup
if ($Backend -or $Both) {
    Write-Header "Setting up Backend"
    
    # Check if venv exists, if not create it
    if (-not (Test-Path "backend\venv")) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        cd backend
        python -m venv venv
        cd ..
    }
    
    # Activate venv and install dependencies
    Write-Host "Activating virtual environment and installing dependencies..." -ForegroundColor Yellow
    cd backend
    & ".\venv\Scripts\Activate.ps1"
    
    if (-not (Test-Path "requirements.txt")) {
        Write-Host "ERROR: requirements.txt not found in backend directory!" -ForegroundColor Red
        exit 1
    }
    
    pip install -q -r requirements.txt
    cd ..
    
    Write-Host "Backend setup complete!" -ForegroundColor Green
}

# Frontend setup
if ($Frontend -or $Both) {
    Write-Header "Setting up Frontend"
    
    Test-PathExists "frontend\package.json"
    
    cd frontend
    
    # Install node modules if not present
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
        npm install
    }
    
    cd ..
    
    Write-Host "Frontend setup complete!" -ForegroundColor Green
}

Write-Header "Starting Development Servers"

# Start Backend
if ($Backend -or $Both) {
    Write-Host "Starting Backend Server (FastAPI)..." -ForegroundColor Green
    $backendCmd = "cd backend; & '.\venv\Scripts\Activate.ps1'; uvicorn main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    Write-Host "Backend server launched in new window on http://127.0.0.1:8000" -ForegroundColor Green
    Start-Sleep -Seconds 2
}

# Start Frontend
if ($Frontend -or $Both) {
    Write-Host "Starting Frontend Server (Vite)..." -ForegroundColor Green
    $frontendCmd = "cd frontend; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    Write-Host "Frontend server launched in new window on http://localhost:5173" -ForegroundColor Green
}

Write-Host "`nDevelopment environment is ready!" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "`nPress Ctrl+C in any window to stop the servers." -ForegroundColor Yellow
