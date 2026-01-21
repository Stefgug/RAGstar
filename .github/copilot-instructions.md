# Copilot Instructions for RAGstar

## Project Overview
RAGstar is a local repository discovery system using vector search. It summarizes GitHub repositories and enables natural language queries to find the right repo.

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
- `src/ragstar/cli.py` - Command-line interface
- `src/ragstar/config.py` - Settings and repository list
- `src/ragstar/index.py` - Build vector index
- `src/ragstar/search.py` - Query vector database
- `src/ragstar/summarizer.py` - Generate repo summaries via Ollama
- `src/ragstar/viewer.py` - View stored summaries

### Configuration
- Settings via environment variables (see README)
- Repository list in `config.py` as `REPOSITORIES`
- Local ChromaDB (no external services)

### Code Patterns
- Use `Settings` dataclass for all config
- ChromaDB operations via helper functions in `config.py`
- CLI uses argparse with subcommands
- Keep main logic in library code, not in CLI

### Simplicity
- Prefer readability over cleverness
- Local-first, no cloud dependencies
- Minimal error handling - fail fast and clear
