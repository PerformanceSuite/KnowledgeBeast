# Production Multi-Stage Dockerfile for KnowledgeBeast
# Stage 1: Builder - Install dependencies and compile wheels
FROM python:3.11-slim AS builder

# Set build environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
WORKDIR /build
COPY requirements.txt pyproject.toml setup.py ./

# Install Python dependencies and build wheels
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Copy application code and install package
COPY knowledgebeast/ ./knowledgebeast/
RUN pip install --no-cache-dir --no-deps .

# Stage 2: Runtime - Minimal production image
FROM python:3.11-slim

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    KB_DATA_DIR=/data \
    KB_CONFIG_DIR=/config \
    KB_LOG_LEVEL=INFO

# Add labels for image metadata
LABEL maintainer="Daniel Connolly <daniel@example.com>" \
      version="0.1.0" \
      description="Production-ready knowledge management system with RAG capabilities" \
      org.opencontainers.image.title="KnowledgeBeast" \
      org.opencontainers.image.description="RAG-powered knowledge management system" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="KnowledgeBeast" \
      org.opencontainers.image.licenses="MIT"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r knowledgebeast --gid=1000 && \
    useradd -r -g knowledgebeast --uid=1000 --home-dir=/app --shell=/bin/bash knowledgebeast

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code from builder
COPY --from=builder --chown=knowledgebeast:knowledgebeast /build/knowledgebeast ./knowledgebeast

# Create necessary directories with proper permissions
RUN mkdir -p /data /config /app/logs && \
    chown -R knowledgebeast:knowledgebeast /app /data /config

# Create volume mount points
VOLUME ["/data", "/config"]

# Switch to non-root user
USER knowledgebeast

# Expose API port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command - run API server
CMD ["uvicorn", "knowledgebeast.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
