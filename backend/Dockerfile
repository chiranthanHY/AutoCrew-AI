# ============================================================
# Dockerfile — AutoCrew AI Backend
# ============================================================
# Multi-stage build optimised for Neon + psycopg3 on Python 3.12.
# ============================================================

# ── Stage 1: Build dependencies ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System packages needed to compile psycopg3 binary and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime image ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Only runtime libs — no build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 autocrew && chown -R autocrew:autocrew /app
USER autocrew

# Create outputs directory for file exports
RUN mkdir -p /app/outputs

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn (production-grade ASGI server)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]
