# Optimized production Dockerfile for Python application using uv
FROM python:3.12.8-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121 \
    UV_PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121

WORKDIR /app

# Copy uv binary from pinned version for reproducibility
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Copy project files (including lockfile)
COPY pyproject.toml uv.lock /app/

# Install dependencies using uv with cache mount for better builds
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --no-install-project

FROM deps AS builder

COPY src /app/src
COPY README.md ragstar.yaml /app/

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev

# Final production stage with minimal footprint
FROM python:3.12.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAGSTAR_CONFIG_PATH=/app/ragstar.yaml \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies and clean up in single layer
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy virtual environment and application files
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src /app/src
COPY --chown=appuser:appuser README.md ragstar.yaml /app/

# Switch to non-root user
USER appuser

EXPOSE 8000

# Use exec form for proper signal handling
CMD ["uvicorn", "ragstar.api:app", "--host", "0.0.0.0", "--port", "8000"]
