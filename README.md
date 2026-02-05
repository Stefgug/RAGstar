# RAGstar

RAG service that helps users find the right GitHub repo by asking a natural language question. It builds an index from repositories fetched from a given GitHub account's starred repos, summarizes them, and lets users query that knowledge base.

Demo: https://stefgug.dev/portfolio/RAGstar

<img width="1376" height="795" alt="image" src="https://github.com/user-attachments/assets/ca49b8dd-0ee4-47c0-a943-616a5650a5b6" />


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
- [Flaskstar](https://github.com/Stefgug/Flaskstar) is the frontend and UI layer.

## GitHub automation

RAGstar is deployed via GitHub Actions:

- Builds the Docker image and tags it
- Pushes to Artifact Registry
- Updates the `ragstar` deployment in the `ragstar` namespace and waits for rollout.

## Hosting

Both containers (RAGstar + Flaskstar) are currently deployed to a GKE cluster on GCP. 



This project is for demo and learning purposes.
