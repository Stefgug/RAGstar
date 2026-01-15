"""
Query Interface - Search repositories by description
"""

import chromadb
from config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME


def search_repositories(query: str, num_results: int = 5) -> list:
    """
    Search for repositories matching a query.

    Args:
        query: Natural language description of what you're looking for
        num_results: Number of results to return

    Returns:
        List of matching repositories with scores
    """
    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_collection(name=CHROMA_COLLECTION_NAME)

    # Query the collection
    results = collection.query(
        query_texts=[query],
        n_results=num_results
    )

    # Format results for display
    formatted_results = []
    for i in range(len(results["ids"][0])):
        repo_id = results["ids"][0][i]
        distance = results["distances"][0][i]
        metadata = results["metadatas"][0][i]
        document = results["documents"][0][i]

        # Convert distance to similarity score (lower distance = higher similarity)
        similarity_score = 1 - (distance / 2)  # Normalize to 0-1

        formatted_results.append({
            "repo_name": metadata["repo_name"],
            "repo_url": metadata["repo_url"],
            "similarity_score": round(similarity_score, 3),
            "summary": document[:200] + "..." if len(document) > 200 else document
        })

    return formatted_results


def display_results(results: list):
    """Pretty print search results."""
    print(f"\nFound {len(results)} matching repositories:\n")

    for idx, result in enumerate(results, 1):
        print(f"{idx}. {result['repo_name']}")
        print(f"   URL: {result['repo_url']}")
        print(f"   Similarity: {result['similarity_score']*100:.1f}%")
        print(f"   Summary: {result['summary']}\n")


if __name__ == "__main__":
    # Example usage
    query = "machine learning forecasting model"
    print(f"Searching for: '{query}'")

    try:
        results = search_repositories(query, num_results=5)
        display_results(results)
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to run 'python build_index.py' first to build the index.")
