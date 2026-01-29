## RAGstar AI coding notes

### Big picture
- FastAPI service in [src/ragstar/api.py](src/ragstar/api.py) exposing build/search/summary endpoints.
- Index pipeline: `/build` or `/build/stream` → `build_index()`/`iter_build_index()` in [src/ragstar/index.py](src/ragstar/index.py) → `generate_summary()` in [src/ragstar/summarizer.py](src/ragstar/summarizer.py) → ChromaDB via `get_collection()` in [src/ragstar/config.py](src/ragstar/config.py).
- Summaries are README-only via gitingest; embeddings stored in ChromaDB (persistent at ./ragstar_db).

### API patterns
- Repo name is derived from GitHub URL (second path segment) in `_repo_name_from_url()`; keep this behavior consistent.
- Streaming progress uses SSE: `/build/stream` yields events with `start`, `progress`, `complete` and totals (see [src/ragstar/index.py](src/ragstar/index.py)).
- `/clear` is admin-protected; requires `admin_token` (see [src/ragstar/api.py](src/ragstar/api.py)).

### Configuration
- YAML config at ./ragstar.yaml (override with `RAGSTAR_CONFIG_PATH`); required `ollama_url` (see [src/ragstar/config.py](src/ragstar/config.py)).
- Embedding model is `sentence-transformers/all-MiniLM-L6-v2` and is cached locally if present; otherwise downloaded via `snapshot_download()`.
- Environment overrides: `RAGSTAR_OLLAMA_URL`, `RAGSTAR_OLLAMA_PULL_URL`, `RAGSTAR_OLLAMA_MODEL`, `RAGSTAR_GITHUB_TOKEN`, `RAGSTAR_ADMIN_TOKEN`, `RAGSTAR_LOG_LEVEL`.

### Workflows
- Install deps: `uv sync` (Python 3.12).
- Run services: `docker-compose up -d`.
- Health check: `GET /health`.

### Code conventions
- Keep response payloads plain dicts; errors use `HTTPException`.
- Logging configured at app startup; modules use `logging.getLogger(__name__)`.
- Avoid changing public endpoint shapes without updating README examples.
