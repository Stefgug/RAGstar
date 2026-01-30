# RAGstar

RAGstar is a small app that helps you find the right GitHub repo by asking a natural language question.

## What it does

1) Fetches repo content.
2) Creates a short summary with Ollama.
3) Stores summaries in ChromaDB.
4) Lets you search with a query.

## Setup

Install dependencies:
```bash
uv sync
```

Python support: CPython >=3.12,<3.13. The Docker image pins Python 3.12.8.

## Configuration (YAML)

RAGstar reads a YAML config file. Default path is ./ragstar.yaml. You can set RAGSTAR_CONFIG_PATH to use a different file.

Minimal example:
```yaml
ollama_url: http://ollama:11434/api/generate
ollama_model_name: mistral
ollama_embedding_model_name: nomic-embed-text
github_token: ""
admin_token: ""
```

ollama_url is required and must be set either in the YAML file or via RAGSTAR_OLLAMA_URL. ollama_pull_url is derived automatically from ollama_url (you can still override it with an env var if needed).

## Environment Overrides (Optional)

You can override a small set of settings using environment variables:

- RAGSTAR_CONFIG_PATH
- RAGSTAR_LOG_LEVEL
- RAGSTAR_OLLAMA_URL
- RAGSTAR_OLLAMA_PULL_URL
- RAGSTAR_OLLAMA_MODEL
- RAGSTAR_OLLAMA_EMBED_MODEL
- RAGSTAR_GITHUB_TOKEN
- RAGSTAR_ADMIN_TOKEN

## Quick Start (Docker)

Start services:
```bash
docker-compose up -d
```

Health check:
```bash
curl http://localhost:8000/health
```

Build the index:
```bash
curl -X POST http://localhost:8000/build \
    -H "Content-Type: application/json" \
    -d '{"repositories": ["https://github.com/github/awesome-copilot"]}'
```

The repo name is deduced from the URL (the second block after github.com).

Query:
```bash
curl -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"query": "vector search", "num_results": 5}'
```

List summaries:
```bash
curl http://localhost:8000/summaries
```

Get one summary:
```bash
curl http://localhost:8000/summaries/awesome-copilot
```

Pull an Ollama model on demand:
```bash
curl -X POST http://localhost:8000/ollama/pull \
    -H "Content-Type: application/json" \
    -d '{"model": "mistral"}'
```

## Security Notes

- The /clear endpoint is protected by an admin token. Set admin_token in YAML or RAGSTAR_ADMIN_TOKEN.
- When admin_token is not set, /clear is disabled.

## Project Layout

- src/ragstar/api.py: FastAPI endpoints
- src/ragstar/config.py: Settings + ChromaDB
- src/ragstar/index.py: Index builder
- src/ragstar/search.py: Hybrid search
- src/ragstar/summarizer.py: Ollama summarizer
