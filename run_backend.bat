@echo off
title SalonAI - FastAPI Backend Server

echo ====================================================
echo   Starting SalonAI FastAPI Backend Server...
echo ====================================================
echo.

if not exist "backend\venv" (
    echo ERROR: Python virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

cd backend
call .\venv\Scripts\activate.bat
echo Backend environment activated.
echo.
echo Launching Uvicorn server on http://127.0.0.1:8000 ...
uvicorn main:app --reload --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 (
    echo.
    echo ERROR: FastAPI server crashed or stopped.
    cd ..
    pause
    exit /b 1
)
cd ..
