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

## Environment Variables

Set these in your shell, a local .env, or your shell profile (not committed):

- RAGSTAR_DB_PATH (default: ./ragstar_db)
- RAGSTAR_COLLECTION (default: repositories)
- RAGSTAR_EMBEDDING_MODEL (default: all-MiniLM-L6-v2)
- RAGSTAR_EMBEDDING_LOCAL_ONLY (default: false)
- RAGSTAR_GITINGEST_MAX_FILE_SIZE_MB (default: 3)
- RAGSTAR_GITINGEST_INCLUDE_PATTERNS (default: empty)
- RAGSTAR_OLLAMA_MODEL (default: mistral)
- RAGSTAR_OLLAMA_TIMEOUT (default: 180)
- RAGSTAR_MAX_PROMPT_CHARS (default: 120000)
- RAGSTAR_MAX_FILES (default: 30)
- RAGSTAR_MAX_FILE_PREVIEW_CHARS (default: 2000)
- GITHUB_TOKEN (optional, for private repos)

Example (shell):
```bash
export RAGSTAR_DB_PATH=./ragstar_db
export RAGSTAR_EMBEDDING_MODEL=bge-large-en-v1.5
```

## Usage

### 1. Add Your Repositories

Edit [src/ragstar/config.py](src/ragstar/config.py) and add your repositories:
```python
REPOSITORIES = [
    {"name": "repo_name_1", "url": "github/awesome-copilot"},
    {"name": "repo_name_2", "url": "HKUDS/LightRAG"},
    {"name": "repo_name_3", "url": "trimstray/the-book-of-secret-knowledge"},
    # Add up to 100+ repos
]
```

### 2. Build the Index

This will generate summaries and build the vector database (one-time setup):
```bash
uv run ragstar build
```

This may take a few minutes on first run as it downloads the AI models (~2GB total).

### 3. Query Repositories

Ask natural language questions:
```bash
uv run ragstar query "which repo does machine learning forecasting"
uv run ragstar query "what repo has API endpoints"
uv run ragstar query "which one implements real-time data processing"
```

Results show:
- Repository name and URL
- Similarity score (higher = better match)
- Preview of the summary

### 4. View or Clear

```bash
uv run ragstar view
uv run ragstar view <repo_name>
uv run ragstar clear
```

## Architecture

- **src/ragstar/config.py**: Configuration and repository list
- **src/ragstar/summarizer.py**: Generates repository summaries using Ollama
- **src/ragstar/config.py**: Settings, DB helpers, and maintenance
- **src/ragstar/index.py**: Processes repos and stores in ChromaDB
- **src/ragstar/search.py**: Searches the vector database
- **src/ragstar/cli.py**: CLI interface

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
