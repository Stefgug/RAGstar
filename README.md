# RAGstar

RAG service that helps users find the right GitHub repo by asking a natural language question. It builds an index from repositories fetched from a given GitHub account's starred repos, summarizes them, and lets users query that knowledge base.

Demo: https://stefgug.dev/portfolio/RAGstar

<img width="1376" height="795" alt="image" src="https://github.com/user-attachments/assets/e388f952-c568-4247-ac66-04c84a879eef" />



## What it does

1) Fetches repository content from a GitHub user's starred repos.
2) Creates short summaries with Ollama.
3) Stores summaries in ChromaDB.
4) Lets you search with a natural language query.

## Models

- Embeddings: `mxbai-embed-large` via Ollama.
- Summaries and query: `mistral` via Ollama.

## OpenAI fallback

If Ollama is unavailable or too slow (over 5 seconds), RAGstar can fall back to OpenAI for
generation and embeddings. For local testing, set `OPENAI_API_KEY` in your environment:

```bash
export OPENAI_API_KEY=your_key_here
```

Optional fallback settings live in [ragstar.yaml](ragstar.yaml):

- `openai_base_url` (default: `https://api.openai.com/v1`)
- `openai_model_name` (default: `gpt-5-mini`)
- `openai_embedding_model_name` (default: `text-embedding-3-small`)
- `openai_timeout` (default: `30`)
- `ollama_fallback_timeout` (default: `5`)

## Project relationships

- RAGstar (this repo) is the backend and the core of the system.
- [Flaskstar](https://github.com/Stefgug/Flaskstar) is the frontend and UI layer.

## GitHub automation

RAGstar is deployed via GitHub Actions:

- Builds the Docker image and tags it
- Pushes to Artifact Registry
- Updates the `ragstar` deployment in the `ragstar` namespace and waits for rollout.

## Hosting

Both containers (RAGstar + Flaskstar) are currently deployed to a GKE cluster on GCP.



This project is for demo and learning purposes.
