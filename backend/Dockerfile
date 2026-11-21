# ==============================================================================
# SalonAI Workforce Management - Production Backend Dockerfile
# Optimized for Render Web Service (supports dynamic $PORT)
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Install system dependencies for C-extensions, PostgreSQL client, and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications first for optimal Docker layer caching
COPY requirements.txt /app/requirements.txt

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . /app

# Ensure required runtime directories exist
RUN mkdir -p /app/logs /app/data

# Expose default port (Render will override PORT dynamically at runtime)
EXPOSE 8000

# Health check to ensure service readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start Uvicorn bound to 0.0.0.0 and dynamic $PORT passed by Render
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
