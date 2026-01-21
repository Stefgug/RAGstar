# Copilot Instructions for RAGstar

## Project Overview
RAGstar is a repository discovery system using hybrid search (BM25 + dense embeddings). It summarizes GitHub repositories via Ollama and enables natural language queries through a REST API.

## Essential Guidelines

### Language & Style
- Python 3.12 (pinned for CUDA compatibility)
- Use `from __future__ import annotations` for forward references
- Prefer dataclasses for configuration
- Keep functions simple and focused

### Dependencies
- Use `uv` for package management (`uv sync`)
- Core stack: FastAPI, ChromaDB, sentence-transformers, Ollama (via requests), gitingest
- Docker for deployment (Dockerfile + docker-compose)
- Avoid adding new dependencies unless essential

### Project Structure
- `src/ragstar/api.py` - FastAPI REST endpoints
- `src/ragstar/config.py` - YAML-based settings, ChromaDB helpers
- `src/ragstar/index.py` - Build vector index from repo summaries
- `src/ragstar/search.py` - Hybrid search (BM25 + dense embeddings)
- `src/ragstar/summarizer.py` - Generate summaries via Ollama, fetch content via gitingest
- `src/ragstar/viewer.py` - View stored summaries

### Configuration
- YAML config file (default: `./ragstar.yaml`)
- Environment variables for overrides (see README)
- Ollama URL required (Docker: `http://ollama:11434/api/generate`)
- Supports offline mode for embedding models

### Code Patterns
- Use `Settings` dataclass (frozen=True) for all config
- ChromaDB operations via `get_collection()` helper in `config.py`
- FastAPI endpoints with Pydantic models for validation
- Keep main logic in library code, not in API layer
- Implement fallback strategies for network operations (see summarizer)
- Return proper HTTP responses with error details

### Search & Summarization
- Hybrid search combines BM25 (lexical) and dense embeddings (semantic)
- Default weights: 60% BM25, 40% dense (configurable)
- Summaries generated via Ollama API (requests library)
- Repo content fetched via gitingest with fallback to docs-only

### Deployment
- Designed for cloud deployment via Docker
- Docker Compose orchestrates RAGstar + Ollama services
- FastAPI runs via uvicorn
- Prefer container-ready patterns
