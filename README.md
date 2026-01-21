# RAGstar - Repository Discovery System

A simple, local, and free system to discover which starred repository does "the thing you want to do".

## How It Works

1. **Summarize**: Generate concise summaries of each repository using a local AI model
2. **Vectorize**: Convert summaries to numerical embeddings using sentence-transformers
3. **Store**: Save embeddings in ChromaDB for fast similarity search
4. **Query**: Ask natural language questions to find the right repository

## Setup

Install dependencies:
```bash
uv sync
```

Python support: CPython >=3.12,<3.13 (3.12.x supported). The Docker image pins Python 3.12.8 for CUDA compatibility with the torch wheel.

## Configuration (YAML)

RAGstar now expects a YAML config file. By default it looks for `./ragstar.yaml`,
or you can set `RAGSTAR_CONFIG_PATH` to point elsewhere.

Example:
```yaml
settings:
    chroma_db_path: ./ragstar_db
    chroma_collection_name: repositories
    embedding_model: all-MiniLM-L6-v2
    embedding_local_only: false
    gitingest_max_file_size_mb: 3
    gitingest_include_patterns: ""
    # Default Ollama endpoints use Docker service name "ollama".
    # For local (non-Docker) Ollama, use:
    #   ollama_url: http://localhost:11434/api/generate
    #   ollama_pull_url: http://localhost:11434/api/pull
    ollama_url: http://ollama:11434/api/generate
    ollama_pull_url: http://ollama:11434/api/pull
    ollama_model_name: mistral
    ollama_timeout: 180
    max_prompt_chars: 120000
    max_files: 30
    max_file_preview_chars: 2000
    github_token: ""
```

`ollama_url` is required and must be set either in the YAML file or via `RAGSTAR_OLLAMA_URL`.

## Environment Overrides (Optional)

You can override any setting using environment variables (useful in containers):

- RAGSTAR_CONFIG_PATH (path to YAML file)
- RAGSTAR_DB_PATH
- RAGSTAR_COLLECTION
- RAGSTAR_EMBEDDING_MODEL
- RAGSTAR_EMBEDDING_LOCAL_ONLY
- RAGSTAR_GITINGEST_MAX_FILE_SIZE_MB
- RAGSTAR_GITINGEST_INCLUDE_PATTERNS
- RAGSTAR_OLLAMA_URL (required if not in YAML)
- RAGSTAR_OLLAMA_PULL_URL
- RAGSTAR_OLLAMA_MODEL
- RAGSTAR_OLLAMA_TIMEOUT
- RAGSTAR_MAX_PROMPT_CHARS
- RAGSTAR_MAX_FILES
- RAGSTAR_MAX_FILE_PREVIEW_CHARS
- RAGSTAR_GITHUB_TOKEN (optional, for private repos)

## Usage (HTTP API)

The RAGstar API is designed for Docker deployment and exposes endpoints on port 8000.

### Quick Start with Docker Compose

```bash
docker-compose up -d
```

This starts both Ollama (for LLM summarization) and RAGstar API services.

Health check:
```bash
curl http://localhost:8000/health
```

Build the index (1..N repos in request body):
```bash
curl -X POST http://localhost:8000/build \
    -H "Content-Type: application/json" \
    -d '{"repositories": [{"name": "awesome-copilot", "url": "https://github.com/github/awesome-copilot"}]}'
```

Query:
```bash
curl -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"query": "which repo does vector search", "num_results": 5}'
```

List summaries:
```bash
curl http://localhost:8000/summaries
```

Get summary by repo name:
```bash
curl http://localhost:8000/summaries/LightRAG
```

Pull an Ollama model on demand:
```bash
curl -X POST http://localhost:8000/ollama/pull \
    -H "Content-Type: application/json" \
    -d '{"model": "mistral"}'
```

## Docker build speedups (CUDA + base image)

The app container pulls `torch` CUDA wheels, which are large. To reduce rebuild time:

1) Prebuild a dependency base layer (cached CUDA wheels):
```bash
docker build --target deps -t ragstar-deps:cu121 .
```

2) Build the app using the cached base:
```bash
docker build --cache-from ragstar-deps:cu121 -t ragstar:latest .
```

If you want a different CUDA version, change the `PIP_EXTRA_INDEX_URL` in the Dockerfile
and the pinned `torch` version in `pyproject.toml` (currently 2.4.1).

## Architecture

RAGstar is designed as a containerized API service with the following components:

- **src/ragstar/api.py**: FastAPI REST endpoints for building indexes and querying
- **src/ragstar/config.py**: YAML-based configuration and ChromaDB client
- **src/ragstar/summarizer.py**: Generates repository summaries using Ollama
- **src/ragstar/index.py**: Processes repositories and stores in ChromaDB
- **src/ragstar/search.py**: Hybrid search (BM25 + dense embeddings) over vector database

## Technical Details

- **Embedding Model**: `all-MiniLM-L6-v2` (default, configurable via `RAGSTAR_EMBEDDING_MODEL`)
- **Summarizer Model**: `mistral` via Ollama (default, configurable)
- **Vector DB**: ChromaDB (local, persistent, no server needed)
- **Everything**: Runs locally, no API keys needed

Avoiding Hugging Face network checks:

- RAGstar now prefers a locally cached copy of the embedding model and will use it if available. This avoids repeated HEAD requests to the HF hub.
- To prefetch a model:

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-large-en-v1.5')"
```

- Or set `RAGSTAR_EMBEDDING_MODEL` to a local path where the model snapshot resides.
- To force strict offline mode (fail if not cached), set `RAGSTAR_EMBEDDING_LOCAL_ONLY=1`.
- You can also set `HF_HUB_OFFLINE=1` (or `TRANSFORMERS_OFFLINE=1`) for strict offline behavior.
