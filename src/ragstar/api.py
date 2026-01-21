"""FastAPI service for RAGstar."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from .config import settings, get_collection, clear_database
from .index import build_index
from .search import search_repositories
from .summarizer import pull_ollama_model

app = FastAPI(title="RAGstar API", version="0.1.0")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    num_results: int = Field(default=5, ge=1, le=50)


class QueryResponse(BaseModel):
    results: list[dict[str, Any]]


class RepoItem(BaseModel):
    name: str = Field(..., min_length=1)
    url: HttpUrl


class BuildRequest(BaseModel):
    repositories: list[RepoItem] = Field(..., min_length=1)


class OllamaPullRequest(BaseModel):
    model: str | None = Field(default=None)
    
    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("model must be a non-empty string or None")
        return v


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> dict[str, Any]:
    data = asdict(settings)
    data["chroma_db_path"] = str(settings.chroma_db_path)
    # Remove sensitive fields before returning configuration
    data.pop("github_token", None)
    return data


@app.post("/build")
def build(payload: BuildRequest) -> dict[str, Any]:
    """Build the index for the provided repositories.
    
    NOTE: This endpoint may take significant time for large repositories or many
    repositories, as it fetches content, generates LLM summaries, and stores results.
    For production use, consider implementing this as a background task with status polling."""
    repos = [{"name": repo.name, "url": str(repo.url)} for repo in payload.repositories]
    results = build_index(repos)
    stored = sum(1 for item in results if item.get("status") == "stored")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    errored = sum(1 for item in results if item.get("status") == "error")
    return {
        "status": "completed",
        "count": len(repos),
        "stored": stored,
        "skipped": skipped,
        "errored": errored,
        "results": results,
    }


@app.post("/query", response_model=QueryResponse)
def query_repositories(payload: QueryRequest) -> QueryResponse:
    results = search_repositories(payload.query, num_results=payload.num_results)
    return QueryResponse(results=results)


@app.get("/summaries")
def list_summaries() -> dict[str, Any]:
    collection = get_collection()
    all_items = collection.get()
    if not all_items.get("ids"):
        return {"count": 0, "items": []}

    items = []
    for repo_id, document, metadata in zip(
        all_items["ids"],
        all_items["documents"],
        all_items["metadatas"],
    ):
        items.append(
            {
                "repo_id": repo_id,
                "repo_name": metadata.get("repo_name"),
                "repo_url": metadata.get("repo_url"),
                "summary_length": metadata.get("summary_length"),
                "summary": document,
            }
        )

    return {"count": len(items), "items": items}


@app.get("/summaries/{repo_name}")
def get_summary(repo_name: str) -> dict[str, Any]:
    collection = get_collection()
    result = collection.get(ids=[repo_name])
    if not result.get("ids"):
        raise HTTPException(status_code=404, detail="Repository not found")

    metadata = result["metadatas"][0]
    document = result["documents"][0]

    return {
        "repo_id": result["ids"][0],
        "repo_name": metadata.get("repo_name"),
        "repo_url": metadata.get("repo_url"),
        "summary_length": metadata.get("summary_length"),
        "summary": document,
    }


@app.post("/clear")
def clear_db() -> dict[str, Any]:
    """Clear the database. WARNING: This endpoint has no authentication and should
    only be exposed in development environments. In production, consider removing
    this endpoint or adding proper authentication."""
    clear_database()
    return {
        "status": "cleared",
        "chroma_db_path": str(settings.chroma_db_path),
    }


@app.post("/ollama/pull")
def pull_model(payload: OllamaPullRequest) -> dict[str, Any]:
    model_name = payload.model or settings.ollama_model_name
    ok = pull_ollama_model(model_name)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to pull Ollama model")
    return {"status": "pulled", "model": model_name}
