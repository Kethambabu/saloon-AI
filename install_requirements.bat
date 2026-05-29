@echo off
title SalonAI - Install & Update Requirements

echo ====================================================
echo   SalonAI Requirements Installer & Updater
echo ====================================================
echo.

:: 1. Backend Python Dependencies
echo Updating Python virtual environment packages...
if exist "backend\venv" (
    cd backend
    call .\venv\Scripts\activate.bat
    echo Upgrading pip...
    python -m pip install --upgrade pip
    echo Installing requirements.txt...
    pip install -r requirements.txt
    cd ..
    echo [OK] Backend dependencies updated successfully.
) else (
    echo WARNING: backend\venv not found. Please run setup.bat first.
)
echo.

:: 2. Frontend Node.js Dependencies
echo Updating Node.js dependencies...
if exist "frontend\package.json" (
    cd frontend
    echo Installing npm dependencies...
    call npm install
    cd ..
    echo [OK] Frontend packages updated successfully.
) else (
    echo WARNING: frontend\package.json not found.
)
echo.

echo ====================================================
echo   Updates completed!
echo ====================================================
echo.
pause
