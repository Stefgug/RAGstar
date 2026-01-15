"""
RAGstar - Repository Discovery System

This script provides a simple interface to:
1. Build the vector index: python ingest.py build
2. Query repositories: python ingest.py query "your question"
3. View stored summaries: python ingest.py view [repo_name]
4. Clear the database: python ingest.py clear
"""

import sys
from build_index import build_index
from query import search_repositories, display_results
from viewer import view_all_summaries, view_summary_by_name
from cleaner import clear_database


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ingest.py build              - Build the vector index")
        print("  python ingest.py query <query>      - Search repositories")
        print("  python ingest.py view               - View all stored summaries")
        print("  python ingest.py view <repo_name>   - View summary for specific repo")
        print("  python ingest.py clear              - Clear the database (start fresh)")
        return

    command = sys.argv[1]

    if command == "build":
        build_index()
    elif command == "query":
        if len(sys.argv) < 3:
            print("Error: Please provide a search query")
            print("Example: python ingest.py query 'what I am looking for'")
            return

        query_text = " ".join(sys.argv[2:])
        print(f"\nSearching for: '{query_text}'")
        results = search_repositories(query_text)
        display_results(results)
    elif command == "view":
        if len(sys.argv) == 2:
            # View all summaries
            view_all_summaries()
        else:
            # View specific repo
            repo_name = sys.argv[2]
            view_summary_by_name(repo_name)
    elif command == "clear":
        clear_database()
    else:
        print(f"Unknown command: {command}")
        print("Use 'build', 'query', 'view', or 'clear'")


if __name__ == "__main__":
    main()
