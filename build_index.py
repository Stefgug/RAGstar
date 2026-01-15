"""
Vector Database Builder - Indexes repositories in ChromaDB
"""

import chromadb
from pathlib import Path
from summarizer import generate_summary
from config import REPOSITORIES, CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL


def initialize_chroma_db():
    """
    Initialize ChromaDB client and collection.

    Returns:
        ChromaDB collection object
    """
    # Create persistent client (saves to disk)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Create or get collection with embedding function
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    return collection


def build_index():
    """
    Process all repositories and store summaries in ChromaDB.
    """
    print(f"Initializing ChromaDB at {CHROMA_DB_PATH}...\n")
    collection = initialize_chroma_db()

    print(f"Building index for {len(REPOSITORIES)} repositories...\n")

    for idx, repo in enumerate(REPOSITORIES, 1):
        repo_name = repo["name"]
        repo_url = repo["url"]

        print(f"[{idx}/{len(REPOSITORIES)}] Processing: {repo_name}")

        # Generate summary
        summary = generate_summary(repo_url, repo_name)
        print(f"  ✓ Summary generated ({len(summary)} chars)")

        # Store in ChromaDB
        # ChromaDB automatically generates embeddings using the default embedding function
        try:
            collection.add(
                ids=[repo_name],
                documents=[summary],
                metadatas=[{
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "summary_length": len(summary)
                }]
            )
            print(f"  ✓ Added to database\n")
        except Exception as e:
            print(f"  ✗ Error storing in database: {e}\n")

    print(f"Index building complete! Stored in {CHROMA_DB_PATH}")


if __name__ == "__main__":
    build_index()
