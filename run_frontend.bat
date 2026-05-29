@echo off
title SalonAI - React Frontend Server

echo ====================================================
echo   Starting SalonAI React Frontend Server...
echo ====================================================
echo.

if not exist "frontend\node_modules" (
    echo ERROR: node_modules not found in frontend directory.
    echo Please run setup.bat first to install Node.js dependencies.
    pause
    exit /b 1
)

cd frontend
echo Launching Vite development server on http://localhost:5173 ...
call npm run dev
if %errorlevel% neq 0 (
    echo.
    echo ERROR: React frontend server stopped or crashed.
    cd ..
    pause
    exit /b 1
)
cd ..
