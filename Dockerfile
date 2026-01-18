FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121 \
    UV_PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu121

WORKDIR /app

# Copy uv binary from official distroless image (pinable via tag if desired)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RAGSTAR_CONFIG_PATH=/app/ragstar.yaml

WORKDIR /app

# Install git for runtime gitingest
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY src /app/src
COPY README.md ragstar.yaml /app/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "ragstar.api:app", "--host", "0.0.0.0", "--port", "8000"]
