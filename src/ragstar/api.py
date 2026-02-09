"""FastAPI service for RAGstar."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.responses import StreamingResponse

from .config import (
    settings,
    clear_database,
    get_embedding_backend_used,
    CHROMA_DB_PATH,
)
from .index import build_index, iter_build_index
from .search import search_repositories, get_summary_by_name, list_all_summaries
from .ollama import pull_ollama_model, call_ollama

# Configure logging at application level
log_level_str = os.getenv("RAGSTAR_LOG_LEVEL", "INFO").upper()
valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
log_level = getattr(logging, log_level_str if log_level_str in valid_levels else "INFO")
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAGstar API", version="0.1.0")


@app.on_event("startup")
def _pull_ollama_models_on_startup() -> None:
    if settings.fireworks_api_key.strip():
        logger.info("Fireworks embedding fallback is configured (FIREWORKS_API_KEY present)")
    else:
        logger.warning("Fireworks embedding fallback is NOT configured (no FIREWORKS_API_KEY)")

    if settings.openai_api_key.strip():
        logger.info("OpenAI generation fallback is configured (OPENAI_API_KEY present)")
    else:
        logger.warning("OpenAI generation fallback is NOT configured (no OPENAI_API_KEY)")

    models = [settings.ollama_model_name, settings.ollama_embedding_model_name]
    unique_models = [name for idx, name in enumerate(models) if name and name not in models[:idx]]
    for model_name in unique_models:
        logger.info(f"Ensuring Ollama model is available: {model_name}")
        if not pull_ollama_model(model_name):
            logger.warning(f"Ollama model pull failed or unavailable: {model_name}")


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
    return {"status": "running"}


@app.get("/config")
def get_config() -> dict[str, Any]:
    # Return only non-sensitive configuration details
    return {
        "embedding_model": settings.ollama_embedding_model_name,
        "ollama_model_name": settings.ollama_model_name,
        "fireworks_fallback": bool(settings.fireworks_api_key.strip()),
        "openai_generation_fallback": bool(settings.openai_api_key.strip()),
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


@app.post("/build/stream")
def build_stream(repositories: list[str] = Body(..., embed=True)) -> StreamingResponse:
    """Build the index and stream progress updates via SSE."""
    repos = [
        {"name": _repo_name_from_url(str(repo_url)), "url": str(repo_url)}
        for repo_url in repositories
    ]

    def event_stream():
        for event in iter_build_index(repos):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
    cleared = clear_database()
    if not cleared:
        raise HTTPException(status_code=500, detail="Failed to clear database")
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


@app.post('/ask')
def ask_question(
    question: str = Body(..., embed=True),
    num_results: int = Body(5, embed=True),
) -> dict[str, Any]:
    """Answer a question using the indexed repository summaries."""
    results = search_repositories(question, num_results=num_results)
    embedding_backend = get_embedding_backend_used()

    # Build context with repository information (optimized for token efficiency)
    repo_contexts = []
    for item in results:
        # Limit summary length to reduce context size and improve speed
        summary = item['summary'][:500] if item['summary'] else ""
        repo_contexts.append(
            f"Repo: {item['repo_name']}\nURL: {item['repo_url']}\nSummary: {summary}"
        )
    combined_context = "\n\n".join(repo_contexts)

    prompt = (
        f"Based on the repository summaries below, answer this question: {question}\n\n"
        f"Repositories:\n{combined_context}\n\n"
        f"Answer concisely with the most relevant repository URL(s):"
    )

    answer, token_info, generation_backend = call_ollama(prompt)
    if answer is None:
        raise HTTPException(status_code=502, detail="Failed to get answer from Ollama")

    return {
        "question": question,
        "answer": answer,
        "sources": results,
        "tokens": token_info,
        "backend": {
            "embedding": embedding_backend,
            "generation": generation_backend,
        },
    }
