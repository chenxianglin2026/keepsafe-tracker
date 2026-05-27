=====================================
HiClaw Installation Log
Started: 2026年 5月27日 星期三 11时55分13秒 CST
User: chenxianglin
System: Darwin chenxianglindeMacBook-Pro-2.local 25.5.0 Darwin Kernel Version 25.5.0: Mon Apr 27 20:41:12 PDT 2026; root:xnu-12377.121.6~2/RELEASE_ARM64_T6050 arm64
Log file: /Users/chenxianglin/hiclaw-install.log
========================================

[HiClaw ERROR] 未找到 docker 或 podman 命令。请先安装 Docker Desktop 或 Podman Desktop：
  Docker Desktop: https://www.docker.com/products/docker-desktop/
  Podman Desktop: https://podman-desktop.io/
chenxianglin@chenxianglindeMacBook-Pro-2 ~ % 
# ============================================================
# KeepSafe Backend — Dockerfile (Multi-stage build)
# ============================================================
# Stage 1: Builder — install Python dependencies
# ============================================================
FROM python:3.11-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2: Runtime — minimal final image
# ============================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# Install runtime system dependencies (only libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd -r keepsafe && useradd -r -g keepsafe -d /app -s /sbin/nologin keepsafe

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code
COPY . .

# Ensure the app directory structure is correct
RUN test -d app && ls app/main.py

# Create credentials directory for FCM/APNs keys (mounted via volume or copied)
RUN mkdir -p /app/credentials

# Change ownership to non-root user
RUN chown -R keepsafe:keepsafe /app

USER keepsafe

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# Run with uvicorn (HTTP/2 support via h2 library)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
