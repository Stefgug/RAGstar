"""Command-line interface for RAGstar."""

from __future__ import annotations

import argparse

from .index import build_index
from .config import clear_database
from .search import search_repositories, display_results
from .viewer import view_all_summaries, view_summary_by_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ragstar", description="Repository discovery via vector search")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="Build the vector index")

    query_parser = sub.add_parser("query", help="Search repositories")
    query_parser.add_argument("query", nargs=argparse.REMAINDER, help="Search query")

    view_parser = sub.add_parser("view", help="View stored summaries")
    view_parser.add_argument("repo_name", nargs="?", help="Specific repo name")

    sub.add_parser("clear", help="Clear the database")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        build_index()
        return

    if args.command == "query":
        if not args.query:
            parser.error("Please provide a search query")
        query_text = " ".join(args.query)
        print(f"\nSearching for: '{query_text}'")
        results = search_repositories(query_text)
        display_results(results)
        return

    if args.command == "view":
        if args.repo_name:
            view_summary_by_name(args.repo_name)
        else:
            view_all_summaries()
        return

    if args.command == "clear":
        clear_database()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
