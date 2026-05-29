@echo off
title SalonAI Platform - Unified Local Setup

echo ====================================================
echo   SalonAI Platform Windows-Native Installer
echo ====================================================
echo.

:: 1. Verify Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not added to your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python detected.

:: 2. Verify Node.js/npm installation
npm -v >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js/npm is not installed or not added to your PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js/npm detected.
echo.

:: 3. Setup root .env file
if not exist ".env" (
    echo Copying .env.example to .env...
    copy ".env.example" ".env" >nul
    echo [OK] Created root .env file. Please open and edit with your Supabase keys.
) else (
    echo [OK] Root .env file already exists.
)
echo.

:: 4. Backend Environment Setup
echo Setting up Python Virtual Environment in backend\venv...
cd backend
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

echo Activating virtualenv and installing Python dependencies...
call .\venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies.
    cd ..
    pause
    exit /b 1
)
echo [OK] Backend dependencies installed successfully.
cd ..
echo.

:: 5. Frontend Node Setup
echo Setting up Node.js dependencies in frontend...
cd frontend
if not exist "node_modules" (
    echo Installing npm dependencies...
    call npm install
) else (
    echo [OK] Node modules already exists.
)
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js packages.
    cd ..
    pause
    exit /b 1
)
echo [OK] Frontend dependencies installed successfully.
cd ..
echo.

echo ====================================================
echo   Local Setup Completed Successfully!
echo ====================================================
echo.
echo Please update your root .env file with your Supabase credentials.
echo.
echo Use the following commands to run the platform:
echo   - Start Backend:   run_backend.bat
echo   - Start Frontend:  run_frontend.bat
echo.
pause
