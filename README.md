# RAGstar - Repository Discovery System

A simple, local, and free system to discover which repository among 100+ repos does "the thing you want to do".

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

## Usage

### 1. Add Your Repositories

Edit `config.py` and add your repositories:
```python
REPOSITORIES = [
    {"name": "repo_name_1", "url": "github / awesome-copilot"},
    {"name": "repo_name_2", "url": "HKUDS / LightRAG "},
    {"name": "repo_name_3", "url": "trimstray / the-book-of-secret-knowledge "},
    # Add up to 100+ repos
]
```

### 2. Build the Index

This will generate summaries and build the vector database (one-time setup):
```bash
uv run python ingest.py build
```

This may take a few minutes on first run as it downloads the AI models (~2GB total).

### 3. Query Repositories

Ask natural language questions:
```bash
uv run python ingest.py query "which repo does machine learning forecasting"
uv run python ingest.py query "what repo has API endpoints"
uv run python ingest.py query "which one implements real-time data processing"
```

Results show:
- Repository name and URL
- Similarity score (higher = better match)
- Preview of the summary

## Architecture

- **config.py**: Configuration and repository list
- **summarizer.py**: Generates repository summaries using transformers
- **build_index.py**: Processes repos and stores in ChromaDB
- **query.py**: Searches the vector database
- **ingest.py**: CLI interface

## Technical Details

- **Embedding Model**: `all-MiniLM-L6-v2` (22MB, very fast)
- **Summarizer Model**: `facebook/bart-large-cnn` (efficient summarization)
- **Vector DB**: ChromaDB (local, persistent, no server needed)
- **Everything**: Runs locally, no API keys needed
