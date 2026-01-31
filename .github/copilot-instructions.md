## RAGstar AI coding notes

### Big picture
- Single FastAPI service in [src/ragstar/api.py](src/ragstar/api.py) with build/query/summary endpoints and admin-only `/clear`.
- Index flow: `/build` or `/build/stream` → `build_index()`/`iter_build_index()` in [src/ragstar/index.py](src/ragstar/index.py) → `generate_summary()` in [src/ragstar/summarizer.py](src/ragstar/summarizer.py) → ChromaDB via `get_collection()` in [src/ragstar/config.py](src/ragstar/config.py).
- Summaries are README-only via gitingest (include pattern `**/README.md`); persistent vectors live in ./ragstar_db.
- Search is hybrid: dense Chroma query + in-code BM25 scoring in [src/ragstar/search.py](src/ragstar/search.py).

### External services & integration points
- Ollama is required for both summarization and embeddings (see [src/ragstar/ollama.py](src/ragstar/ollama.py) and [src/ragstar/config.py](src/ragstar/config.py)).
- Embeddings come from Ollama’s `/api/embeddings` using `ollama_embedding_model_name` (default: `nomic-embed-text`).
- Ollama model pulls are handled via `/api/pull` and exposed at `/ollama/pull`.

### Configuration & conventions
- YAML config at [ragstar.yaml](ragstar.yaml) (override with `RAGSTAR_CONFIG_PATH`); required `ollama_url`.
- Env overrides: `RAGSTAR_OLLAMA_URL`, `RAGSTAR_OLLAMA_PULL_URL`, `RAGSTAR_OLLAMA_MODEL`, `RAGSTAR_OLLAMA_EMBED_MODEL`, `RAGSTAR_GITHUB_TOKEN`, `RAGSTAR_ADMIN_TOKEN`, `RAGSTAR_LOG_LEVEL`.
- Repo name derivation is strict: second path segment of GitHub URL in `_repo_name_from_url()` in [src/ragstar/api.py](src/ragstar/api.py).
- Streaming build uses SSE events `start`/`progress`/`complete` in [src/ragstar/index.py](src/ragstar/index.py).

### Developer workflows
- Install deps: `uv sync` (Python 3.12).
- Run services: `docker-compose up -d` (starts Ollama + RAGstar).
- Health check: `GET /health`.

### API response patterns
- Endpoints return plain dicts; errors use `HTTPException` (see [src/ragstar/api.py](src/ragstar/api.py)).
- If you change endpoint shapes or config keys, update examples in [README.md](README.md).
