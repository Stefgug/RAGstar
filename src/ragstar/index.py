"""Vector index builder."""

from __future__ import annotations

from .config import REPOSITORIES, settings, get_collection
from .summarizer import generate_summary


def build_index() -> None:
    print(f"Initializing ChromaDB at {settings.chroma_db_path}...\n")
    collection = get_collection()

    print(f"Building index for {len(REPOSITORIES)} repositories...\n")

    for idx, repo in enumerate(REPOSITORIES, 1):
        repo_name = repo["name"]
        repo_url = repo["url"]

        print(f"[{idx}/{len(REPOSITORIES)}] Processing: {repo_name}")

        summary = generate_summary(repo_url, repo_name)
        if not summary:
            print("  ✗ Summary skipped (fetch failed)")
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
        except Exception as exc:
            print(f"  ✗ Error storing in database: {exc}\n")

    print(f"Index building complete! Stored in {settings.chroma_db_path}")
