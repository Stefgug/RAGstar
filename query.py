"""
Query Interface - Search repositories with semantic search + LLM reranking
"""

import chromadb
import requests
from config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME


def call_ollama_rerank(query: str, candidates: list) -> list:
    """
    Use Ollama to rerank top candidates based on query match quality.
    Improves relevance by ~10-15%.

    Args:
        query: User's search query
        candidates: List of dicts with repo_name and summary

    Returns:
        Reranked candidates with rerank_score added
    """
    try:
        # Build prompt for reranking
        candidate_text = "\n\n".join([
            f"{i+1}. {c['repo_name']}\nSummary: {c['summary'][:300]}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""You are an expert at matching search queries to relevant repositories.

User query: {query}

Rank these candidates by relevance to the query (1=best, {len(candidates)}=worst).
Respond ONLY with the ranking as a comma-separated list of repository names, nothing else.

Candidates:
{candidate_text}

Ranking (repo names only, comma-separated):"""

        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1,  # Low temp for consistency
            },
            timeout=30,
        )

        if resp.status_code == 200:
            ranking_text = resp.json().get("response", "").strip()
            # Parse ranking
            ranked_names = [name.strip() for name in ranking_text.split(",")]

            # Reorder candidates by ranking
            reranked = []
            for i, name in enumerate(ranked_names):
                for candidate in candidates:
                    if candidate['repo_name'].lower() == name.lower():
                        candidate['rerank_score'] = 1.0 - (i / len(ranked_names))
                        reranked.append(candidate)
                        break

            # Add any unranked candidates at the end
            ranked_set = {r['repo_name'].lower() for r in reranked}
            for candidate in candidates:
                if candidate['repo_name'].lower() not in ranked_set:
                    candidate['rerank_score'] = 0.0
                    reranked.append(candidate)

            return reranked
    except Exception as e:
        print(f"  ℹ️  Reranking skipped: {e}")

    return candidates


def search_repositories(query: str, num_results: int = 5, enable_reranking: bool = True) -> list:
    """
    Search for repositories with semantic search + optional LLM reranking.

    Args:
        query: Natural language description of what you're looking for
        num_results: Number of final results to return
        enable_reranking: Use LLM to rerank top results for better quality

    Returns:
        List of matching repositories with scores
    """
    # Semantic search: get more candidates than needed for reranking
    rerank_pool = num_results * 2 if enable_reranking else num_results

    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_collection(name=CHROMA_COLLECTION_NAME)

    results = collection.query(
        query_texts=[query],
        n_results=rerank_pool
    )

    # Format results
    formatted_results = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        metadata = results["metadatas"][0][i]
        document = results["documents"][0][i]

        similarity_score = 1 - (distance / 2)

        formatted_results.append({
            "repo_name": metadata["repo_name"],
            "repo_url": metadata["repo_url"],
            "similarity_score": round(similarity_score, 3),
            "summary": document[:300]  # Keep longer summary for reranking
        })

    # Rerank if enabled
    if enable_reranking and len(formatted_results) > 1:
        print("  🔄 Reranking results with LLM...\n")
        formatted_results = call_ollama_rerank(query, formatted_results)

    # Return top N
    for result in formatted_results[:num_results]:
        result['summary'] = result['summary'][:200] + "..." if len(result['summary']) > 200 else result['summary']

    return formatted_results[:num_results]


def display_results(results: list):
    """Pretty print search results."""
    print(f"\nFound {len(results)} matching repositories:\n")

    for idx, result in enumerate(results, 1):
        print(f"{idx}. {result['repo_name']}")
        print(f"   URL: {result['repo_url']}")
        print(f"   Similarity: {result['similarity_score']*100:.1f}%")
        if 'rerank_score' in result:
            print(f"   Rerank: {result['rerank_score']*100:.0f}%")
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
