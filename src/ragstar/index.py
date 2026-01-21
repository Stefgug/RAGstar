"""Vector index builder."""

from __future__ import annotations

import logging

from .config import settings, get_collection
from .summarizer import generate_summary

logger = logging.getLogger(__name__)


def build_index(repositories: list[dict[str, str]]) -> list[dict[str, object]]:
    logger.info(f"Initializing ChromaDB at {settings.chroma_db_path}")
    collection = get_collection()

    logger.info(f"Building index for {len(repositories)} repositories")

    results: list[dict[str, object]] = []

    for idx, repo in enumerate(repositories, 1):
        repo_name = repo["name"]
        repo_url = repo["url"]

        logger.info(f"[{idx}/{len(repositories)}] Processing: {repo_name}")

        summary = generate_summary(repo_url, repo_name)
        if not summary:
            logger.warning(f"Summary skipped for {repo_name} (fetch failed)")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "skipped",
                    "reason": "fetch_failed_or_empty",
                }
            )
            continue

        logger.info(f"Summary generated for {repo_name} ({len(summary)} chars)")

        try:
            collection.upsert(
                ids=[repo_name],
                documents=[summary],
                metadatas=[{
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "summary_length": len(summary),
                }],
            )
            logger.info(f"Added/updated {repo_name} in database")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "stored",
                    "summary_length": len(summary),
                }
            )
        except Exception as exc:
            logger.error(f"Error storing {repo_name} in database: {exc}")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "error",
                    "reason": str(exc),
                }
            )

    logger.info(f"Index building complete! Stored in {settings.chroma_db_path}")
    return results
