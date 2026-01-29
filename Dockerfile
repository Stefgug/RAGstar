# Dockerfile for RAGstar
FROM python:3.12.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/app/.cache/uv \
    XDG_CACHE_HOME=/app/.cache \
    HOME=/app \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121 \
    UV_PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md /app/

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev --no-install-project

COPY src /app/src
RUN rm -rf /app/src/*.egg-info
COPY ragstar.yaml /app/

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAGSTAR_CONFIG_PATH=/app/ragstar.yaml \
    UV_CACHE_DIR=/app/.cache/uv \
    XDG_CACHE_HOME=/app/.cache \
    HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

RUN mkdir -p /app/ragstar_db /app/.cache/huggingface /app/.cache/uv \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "ragstar.api:app", "--host", "0.0.0.0", "--port", "8000"]
