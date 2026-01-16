"""View summaries stored in ChromaDB."""

from __future__ import annotations

from chromadb import PersistentClient

from .config import settings


def view_all_summaries() -> None:
    try:
        client = PersistentClient(path=str(settings.chroma_db_path))
        collection = client.get_collection(name=settings.chroma_collection_name)
        all_items = collection.get()

        if not all_items.get("ids"):
            print("No repositories stored yet. Run 'ragstar build' first.")
            return

        print(f"\n{'='*80}")
        print(f"Stored Summaries ({len(all_items['ids'])} repositories)")
        print(f"{'='*80}\n")

        for idx, (repo_id, document, metadata) in enumerate(
            zip(all_items["ids"], all_items["documents"], all_items["metadatas"]),
            1,
        ):
            print(f"{idx}. {metadata['repo_name']}")
            print(f"   URL: {metadata['repo_url']}")
            print(f"   Summary length: {metadata['summary_length']} chars\n")
            print(f"   Summary:\n   {document}\n")
            print(f"{'-'*80}\n")

    except Exception as exc:
        print(f"Error: {exc}")
        print("Make sure to run 'ragstar build' first to build the index.")


def view_summary_by_name(repo_name: str) -> None:
    try:
        client = PersistentClient(path=str(settings.chroma_db_path))
        collection = client.get_collection(name=settings.chroma_collection_name)
        result = collection.get(ids=[repo_name])

        if not result.get("ids"):
            print(f"Repository '{repo_name}' not found.")
            return

        metadata = result["metadatas"][0]
        document = result["documents"][0]

        print(f"\n{'='*80}")
        print(f"Summary for: {metadata['repo_name']}")
        print(f"{'='*80}\n")
        print(f"URL: {metadata['repo_url']}")
        print(f"Summary length: {metadata['summary_length']} chars\n")
        print(f"Summary:\n{document}\n")

    except Exception as exc:
        print(f"Error: {exc}")
        print("Make sure to run 'ragstar build' first to build the index.")
