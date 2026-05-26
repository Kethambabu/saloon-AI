.PHONY: help setup install install-backend install-frontend \
	dev dev-backend dev-frontend lint format test \
	clean freeze update-requirements

help:
	@echo "SalonAI Workforce - Development Commands"
	@echo "========================================"
	@echo "setup              - Complete setup (venv + dependencies)"
	@echo "install            - Install all dependencies"
	@echo "install-backend    - Install backend dependencies"
	@echo "install-frontend   - Install frontend dependencies"
	@echo "dev                - Start both frontend and backend"
	@echo "dev-backend        - Start backend server only"
	@echo "dev-frontend       - Start frontend server only"
	@echo "lint               - Run all linters"
	@echo "lint-backend       - Lint backend code"
	@echo "lint-frontend      - Lint frontend code"
	@echo "format             - Format all code"
	@echo "format-backend     - Format backend code"
	@echo "format-frontend    - Format frontend code"
	@echo "test               - Run all tests"
	@echo "test-backend       - Run backend tests"
	@echo "test-frontend      - Run frontend tests"
	@echo "freeze             - Update requirements.txt"
	@echo "clean              - Clean build artifacts"

setup:
	@echo "Setting up development environment..."
	@cd backend && python -m venv venv
	@echo "Backend venv created"
	$(MAKE) install

install: install-backend install-frontend
	@echo "All dependencies installed!"

install-backend:
	@echo "Installing backend dependencies..."
	@cd backend && ./venv/Scripts/pip install -r requirements.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	@cd frontend && npm install

dev:
	@echo "Starting development servers..."
	@echo "Frontend will start on http://localhost:5173"
	@echo "Backend will start on http://127.0.0.1:8000"
	@powershell -NoExit -Command "$$PSVersionTable; cd frontend; npm run dev" &
	@cd backend && ./venv/Scripts/uvicorn main:app --reload

dev-backend:
	@cd backend && ./venv/Scripts/uvicorn main:app --reload

dev-frontend:
	@cd frontend && npm run dev

lint: lint-backend lint-frontend

lint-backend:
	@echo "Linting backend code..."
	@cd backend && ./venv/Scripts/pylint core/ main.py

lint-frontend:
	@echo "Linting frontend code..."
	@cd frontend && npm run lint

format: format-backend format-frontend
	@echo "All code formatted!"

format-backend:
	@echo "Formatting backend code..."
	@cd backend && ./venv/Scripts/black . --line-length 100

format-frontend:
	@echo "Formatting frontend code..."
	@cd frontend && npm run format

test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	@cd backend && ./venv/Scripts/pytest tests/ -v

test-frontend:
	@echo "Running frontend tests..."
	@cd frontend && npm test

freeze:
	@echo "Updating requirements.txt..."
	@cd backend && ./venv/Scripts/pip freeze > requirements.txt
	@echo "requirements.txt updated!"

update-requirements: freeze

clean:
	@echo "Cleaning build artifacts..."
	@cd frontend && rm -rf dist build .next coverage
	@cd backend && rm -rf build dist *.egg-info .pytest_cache .mypy_cache
	@echo "Clean complete!"

type-check:
	@echo "Type checking..."
	@cd frontend && npm run type-check
	@echo "Frontend type check passed!"

.DEFAULT_GOAL := help
