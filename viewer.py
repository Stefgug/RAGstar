"""
View summaries stored in ChromaDB
"""

import chromadb
from config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME


def view_all_summaries():
    """Display all stored repository summaries."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME)

        # Get all items in the collection
        all_items = collection.get()

        if not all_items["ids"]:
            print("No repositories stored yet. Run 'python ingest.py build' first.")
            return

        print(f"\n{'='*80}")
        print(f"Stored Summaries ({len(all_items['ids'])} repositories)")
        print(f"{'='*80}\n")

        for idx, (repo_id, document, metadata) in enumerate(
            zip(all_items["ids"], all_items["documents"], all_items["metadatas"]),
            1
        ):
            print(f"{idx}. {metadata['repo_name']}")
            print(f"   URL: {metadata['repo_url']}")
            print(f"   Summary length: {metadata['summary_length']} chars\n")
            print(f"   Summary:\n   {document}\n")
            print(f"{'-'*80}\n")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to run 'python ingest.py build' first to build the index.")


def view_summary_by_name(repo_name: str):
    """Display summary for a specific repository."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME)

        # Get specific item
        result = collection.get(ids=[repo_name])

        if not result["ids"]:
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

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to run 'python ingest.py build' first to build the index.")


if __name__ == "__main__":
    view_all_summaries()
