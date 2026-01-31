# Dockerfile for RAGstar - Production Optimized
# Multi-stage build for minimal final image size

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.12.8-slim AS builder

# Build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install build dependencies and uv in a single layer
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    pip install --no-cache-dir uv==0.5.11

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies without the project itself
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev --no-install-project --frozen

# Copy source code and install the project
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev --frozen && \
    rm -rf src/*.egg-info

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12.8-slim AS runtime

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAGSTAR_CONFIG_PATH=/app/ragstar.yaml \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/app

WORKDIR /app

# Install only essential runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user and group early
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -s /sbin/nologin -c "Application user" appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application source and configuration
COPY --chown=appuser:appuser src /app/src
COPY --chown=appuser:appuser ragstar.yaml /app/

# Trust the Ollama proxy CA (self-signed) for outbound HTTPS
COPY ollama-ca.crt /usr/local/share/ca-certificates/ollama-ca.crt
RUN update-ca-certificates

# Create necessary directories with proper permissions
RUN mkdir -p /app/ragstar_db /app/.cache && \
    chown appuser:appuser /app/ragstar_db /app/.cache

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "ragstar.api:app", "--host", "0.0.0.0", "--port", "8000"]
