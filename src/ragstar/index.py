"""Vector index builder."""

from __future__ import annotations

from .config import settings, get_collection
from .summarizer import generate_summary


def build_index(repositories: list[dict[str, str]]) -> list[dict[str, object]]:
    print(f"Initializing ChromaDB at {settings.chroma_db_path}...\n")
    collection = get_collection()

    print(f"Building index for {len(repositories)} repositories...\n")

    results: list[dict[str, object]] = []

    for idx, repo in enumerate(repositories, 1):
        repo_name = repo["name"]
        repo_url = repo["url"]

        print(f"[{idx}/{len(repositories)}] Processing: {repo_name}")

        summary = generate_summary(repo_url, repo_name)
        if not summary:
            print("  ✗ Summary skipped (fetch failed)")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "skipped",
                    "reason": "fetch_failed_or_empty",
                }
            )
            continue

        print(f"  ✓ Summary generated ({len(summary)} chars)")

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
            print("  ✓ Added/updated in database\n")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "stored",
                    "summary_length": len(summary),
                }
            )
        except Exception as exc:
            print(f"  ✗ Error storing in database: {exc}\n")
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "status": "error",
                    "reason": str(exc),
                }
            )

    print(f"Index building complete! Stored in {settings.chroma_db_path}")
    return results
