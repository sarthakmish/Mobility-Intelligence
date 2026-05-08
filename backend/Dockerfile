# ============================================================
# MOBILITY INTELLIGENCE — Backend API Container
# Python 3.11 slim + FastAPI + AI Agent System
# ============================================================

FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies needed for:
# - asyncpg: PostgreSQL async driver (needs libpq-dev)
# - httpx: HTTP client for LLM API calls
# - lxml: XML parsing for web scraping
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend application code
COPY . .

# Expose the API port (Railway injects $PORT at runtime)
EXPOSE 8001

# Production: no --reload. Railway sets PORT env var automatically.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}"]
