"""FastAPI service for RAGstar."""

import logging
import os
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Body

from .config import (
    settings,
    clear_database,
    CHROMA_DB_PATH,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_LOCAL_ONLY,
    GITINGEST_MAX_FILE_SIZE_MB,
    GITINGEST_INCLUDE_PATTERNS,
    OLLAMA_TIMEOUT,
    MAX_PROMPT_CHARS,
    MAX_FILES,
    MAX_FILE_PREVIEW_CHARS,
)
from .index import build_index
from .search import search_repositories, get_summary_by_name, list_all_summaries
from .summarizer import pull_ollama_model

# Configure logging at application level
log_level_str = os.getenv("RAGSTAR_LOG_LEVEL", "INFO").upper()
valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
log_level = getattr(logging, log_level_str if log_level_str in valid_levels else "INFO")
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAGstar API", version="0.1.0")


def _require_admin_token(x_admin_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="Admin token not configured")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _repo_name_from_url(repo_url: str) -> str:
    if "github.com" not in repo_url:
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported")
    path_part = repo_url.split("github.com", 1)[1].lstrip("/")
    parts = [part for part in path_part.split("/") if part]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid repository URL")
    repo_name = parts[1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[: -len(".git")]
    if not repo_name:
        raise HTTPException(status_code=400, detail="Invalid repository URL")
    return repo_name


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> dict[str, Any]:
    # Return only non-sensitive configuration details
    return {
        "embedding_model": EMBEDDING_MODEL,
        "ollama_model_name": settings.ollama_model_name,
        "max_prompt_chars": MAX_PROMPT_CHARS,
        "max_files": MAX_FILES,
    }


@app.post("/build")
def build(repositories: list[str] = Body(..., embed=True)) -> dict[str, Any]:
    """Build the index for the provided repositories."""
    repos = [
        {"name": _repo_name_from_url(str(repo_url)), "url": str(repo_url)}
        for repo_url in repositories
    ]
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


@app.post("/query")
def query_repositories(
    query: str = Body(...),
    num_results: int = Body(5),
) -> dict[str, Any]:
    results = search_repositories(query, num_results=num_results)
    return {"results": results}


@app.get("/summaries")
def list_summaries() -> dict[str, Any]:
    return list_all_summaries()


@app.get("/summaries/{repo_name}")
def get_summary(repo_name: str) -> dict[str, Any]:
    result = get_summary_by_name(repo_name)
    if not result:
        raise HTTPException(status_code=404, detail="Repository not found")
    return result


@app.post("/clear")
def clear_db(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Clear the database (admin token required)."""
    _require_admin_token(x_admin_token)
    clear_database()
    return {
        "status": "cleared",
        "chroma_db_path": str(CHROMA_DB_PATH),
    }


@app.post("/ollama/pull")
def pull_model(model: str | None = Body(default=None, embed=True)) -> dict[str, Any]:
    model_name = model.strip() if model else settings.ollama_model_name
    if not model_name:
        raise HTTPException(status_code=400, detail="model must be a non-empty string")
    ok = pull_ollama_model(model_name)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to pull Ollama model")
    return {"status": "pulled", "model": model_name}
