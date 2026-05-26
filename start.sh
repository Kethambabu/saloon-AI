#!/bin/bash
# start.sh
# Startup script for SalonAI Workforce Development Environment
# For macOS and Linux users

set -e

FRONTEND_ONLY=false
BACKEND_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --frontend)
            FRONTEND_ONLY=true
            shift
            ;;
        --backend)
            BACKEND_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./start.sh [--frontend|--backend]"
            exit 1
            ;;
    esac
done

# If no flags specified, start both
if [ "$FRONTEND_ONLY" = false ] && [ "$BACKEND_ONLY" = false ]; then
    FRONTEND_ONLY=true
    BACKEND_ONLY=true
fi

echo "================================"
echo "SalonAI Workforce Development Environment"
echo "================================"

# Check for required directories
if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "ERROR: Required directories not found!"
    exit 1
fi

# Backend setup and start
if [ "$BACKEND_ONLY" = true ]; then
    echo ""
    echo "Setting up Backend..."
    cd backend
    
    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python3.11 -m venv venv
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Install dependencies
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies..."
        pip install -q -r requirements.txt
    fi
    
    echo "Backend setup complete!"
    echo ""
    echo "Starting Backend Server..."
    uvicorn main:app --reload --host 127.0.0.1 --port 8000 &
    BACKEND_PID=$!
    cd ..
fi

# Frontend setup and start
if [ "$FRONTEND_ONLY" = true ]; then
    echo ""
    echo "Setting up Frontend..."
    cd frontend
    
    # Install dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install
    fi
    
    echo "Frontend setup complete!"
    echo ""
    echo "Starting Frontend Server..."
    npm run dev &
    FRONTEND_PID=$!
    cd ..
fi

echo ""
echo "================================"
echo "Development Environment Ready!"
echo "================================"
echo "Frontend: http://localhost:5173"
echo "Backend:  http://127.0.0.1:8000"
echo ""
echo "Press Ctrl+C to stop the servers"
echo ""

# Wait for both processes
wait
