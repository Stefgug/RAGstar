# Copilot Instructions for RAGstar

## Project Overview
RAGstar is a local repository discovery system using hybrid search (BM25 + dense embeddings). It summarizes GitHub repositories via local Ollama and enables natural language queries.

## Essential Guidelines

### Language & Style
- Python 3.12+ with type hints
- Use `from __future__ import annotations` for forward references
- Prefer dataclasses for configuration
- Keep functions simple and focused

### Dependencies
- Use `uv` for package management (`uv sync`, `uv run`)
- Core stack: ChromaDB, sentence-transformers, Ollama (via requests), gitingest
- Avoid adding new dependencies unless essential

### Project Structure
- `src/ragstar/cli.py` - Command-line interface (argparse subcommands)
- `src/ragstar/config.py` - Settings, repository list, ChromaDB helpers
- `src/ragstar/index.py` - Build vector index from repo summaries
- `src/ragstar/search.py` - Hybrid search (BM25 + dense embeddings)
- `src/ragstar/summarizer.py` - Generate summaries via Ollama, fetch content via gitingest
- `src/ragstar/viewer.py` - View stored summaries

### Configuration
- Settings via environment variables (see README)
- Repository list in `config.py` as `REPOSITORIES` (list of dicts with name/url)
- Local ChromaDB (no external services)
- Supports offline mode for embedding models

### Code Patterns
- Use `Settings` dataclass (frozen=True) for all config
- ChromaDB operations via `get_collection()` helper in `config.py`
- CLI uses argparse with subcommands (build, query, view, clear)
- Keep main logic in library code, not in CLI
- Implement fallback strategies for network operations (see summarizer)
- Return `None` or empty results on failure, print errors to console

### Search & Summarization
- Hybrid search combines BM25 (lexical) and dense embeddings (semantic)
- Default weights: 60% BM25, 40% dense (configurable)
- Summaries generated via local Ollama API (requests library)
- Repo content fetched via gitingest with fallback to docs-only

### Simplicity
- Prefer readability over cleverness
- Local-first, no cloud dependencies
- Print progress and errors to console
- Fail gracefully with informative messages
