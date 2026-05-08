# ============================================================
# MOBILITY INTELLIGENCE — Backend API Container
# Python 3.11 slim + FastAPI + AI Agent System
# ============================================================

FROM python:3.11-slim-bullseye

# Set working directory inside container
WORKDIR /app

# Install system dependencies:
# - gcc: needed to compile lxml, asyncpg C extensions
# - curl: healthcheck utility
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker cache layer)
# Build context is repo root, so prefix paths with backend/
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend application code
COPY backend/ .

# Copy startup script
COPY backend/startup.py /app/startup.py

# Expose the API port (Railway injects $PORT at runtime)
EXPOSE 8001

# Run migrations + seeds + start server (Python avoids CRLF shell issues)
CMD ["python", "startup.py"]
