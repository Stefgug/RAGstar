# RAGstar

RAGstar is the main project: a RAG service that helps users find the right GitHub repo by asking a natural language question. It builds an index from repositories fetched from a given GitHub account's starred repos, summarizes them, and lets users query that knowledge base.

Demo: https://stefgug.dev/portfolio/RAGstar

## What it does

1) Fetches repository content from a GitHub user's starred repos.
2) Creates short summaries with Ollama.
3) Stores summaries in ChromaDB.
4) Lets you search with a natural language query.

## Models

- Embeddings: `mxbai-embed-large` via Ollama.
- Summaries and query: `mistral` via Ollama.

## Project relationships

- RAGstar (this repo) is the backend and the core of the system.
- Flaskstar is the frontend and UI layer.

## GitHub automation

RAGstar is deployed via GitHub Actions (`.github/workflows/gcp-build-push.yml`). On push to `master` (or manual dispatch), the workflow:

- Builds the Docker image and tags it with the Git SHA.
- Pushes to Artifact Registry
- Uses Workload Identity for auth and writes the Ollama CA cert from a GitHub secret.
- Updates the `ragstar` deployment in the `ragstar` namespace and waits for rollout.

## Hosting

Both containers (RAGstar + Flaskstar) are currently deployed to a GKE cluster on GCP. This project is for demo and learning purposes.

## Ollama TLS

The GKE deployment trusts Caddy's internal CA for `ollama.local`. If the Caddy data volume is reset, the CA rotates and the backend will fail TLS verification until the secret is updated.

To refresh the CA:

```bash
scripts/export-ollama-ca.sh
```

Update the GitHub secret `OLLAMA_CA_CRT` with the new `ollama-ca.crt` contents, then re-deploy. The workflow syncs the `ollama-ca` Kubernetes secret on deploy.

For a quick in-cluster update without a full redeploy:

```bash
scripts/update-ollama-ca-k8s.sh
```

This exports the local Caddy CA, updates the `ollama-ca` secret, and restarts the `ragstar` deployment.

## Project layout

- src/ragstar/api.py: FastAPI endpoints
- src/ragstar/config.py: Settings + ChromaDB
- src/ragstar/index.py: Index builder
- src/ragstar/search.py: Hybrid search
- src/ragstar/summarizer.py: Ollama summarizer
