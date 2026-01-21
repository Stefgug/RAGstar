"""Query interface - hybrid retrieval (BM25 + dense embeddings)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .config import get_collection


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def compute_bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    avg_doc_length: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    doc_length = len(doc_tokens)
    doc_term_freq = Counter(doc_tokens)
    score = 0.0

    for token in query_tokens:
        if token in doc_term_freq:
            tf = doc_term_freq[token]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
            score += numerator / denominator

    return score


def search_repositories(
    query: str,
    num_results: int = 5,
    dense_weight: float = 0.4,
    bm25_weight: float = 0.6,
) -> list[dict[str, object]]:
    collection = get_collection()
    all_docs = collection.get()

    if not all_docs.get("documents"):
        return []

    query_tokens = tokenize(query)
    all_doc_tokens = [tokenize(doc) for doc in all_docs["documents"]]
    avg_doc_length = sum(len(tokens) for tokens in all_doc_tokens) / len(all_doc_tokens)

    dense_results = collection.query(
        query_texts=[query],
        n_results=len(all_docs["documents"]),
    )

    hybrid_results = []
    for i in range(len(dense_results["ids"][0])):
        distance = dense_results["distances"][0][i]
        metadata = dense_results["metadatas"][0][i]
        document = dense_results["documents"][0][i]

        dense_score = 1 - (distance / 2)
        doc_tokens = tokenize(document)
        bm25_score = compute_bm25_score(query_tokens, doc_tokens, avg_doc_length)
        bm25_normalized = min(bm25_score / 10.0, 1.0) if bm25_score > 0 else 0.0

        hybrid_score = (dense_weight * dense_score) + (bm25_weight * bm25_normalized)

        hybrid_results.append({
            "repo_name": metadata["repo_name"],
            "repo_url": metadata["repo_url"],
            "hybrid_score": round(hybrid_score, 3),
            "dense_score": round(dense_score, 3),
            "bm25_score": round(bm25_normalized, 3),
            "summary": document,
        })

    hybrid_results.sort(key=lambda x: x["hybrid_score"], reverse=True)

    for result in hybrid_results[:num_results]:
        summary = result["summary"]
        result["summary"] = summary[:200] + "..." if len(summary) > 200 else summary

    return hybrid_results[:num_results]


def get_summary_by_name(repo_name: str) -> dict[str, Any] | None:
    """Get a single repository summary by name.
    
    Returns a dictionary with repo details and summary, or None if not found.
    """
    collection = get_collection()
    result = collection.get(ids=[repo_name])
    if not result.get("ids"):
        return None

    metadata = result["metadatas"][0]
    document = result["documents"][0]

    return {
        "repo_id": result["ids"][0],
        "repo_name": metadata.get("repo_name"),
        "repo_url": metadata.get("repo_url"),
        "summary_length": metadata.get("summary_length"),
        "summary": document,
    }


def list_all_summaries() -> dict[str, Any]:
    """List all stored repository summaries.
    
    Returns a dictionary with count and list of all summaries.
    """
    collection = get_collection()
    all_items = collection.get()
    if not all_items.get("ids"):
        return {"count": 0, "items": []}

    items = []
    for repo_id, document, metadata in zip(
        all_items["ids"],
        all_items["documents"],
        all_items["metadatas"],
    ):
        items.append(
            {
                "repo_id": repo_id,
                "repo_name": metadata.get("repo_name"),
                "repo_url": metadata.get("repo_url"),
                "summary_length": metadata.get("summary_length"),
                "summary": document,
            }
        )

    return {"count": len(items), "items": items}
