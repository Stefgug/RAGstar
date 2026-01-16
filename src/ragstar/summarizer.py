"""Repository summarization using local Ollama."""

from __future__ import annotations

import re
from typing import Iterable

import requests
import gitingest

from .config import settings


# -------- Ingest helpers -------- #


def _iter_ingest_attempts() -> list[tuple[int, str | set[str] | None, str]]:
    max_size_bytes = max(1, settings.gitingest_max_file_size_mb) * 1024 * 1024

    attempts: list[tuple[int, str | set[str] | None, str]] = []
    include_patterns = settings.gitingest_include_patterns.strip() or None
    attempts.append((max_size_bytes, include_patterns, "primary"))

    fallback_patterns: set[str] = {
        "**/README*",
        "**/*.md",
        "**/*.rst",
        "**/*.txt",
    }
    fallback_size = min(max_size_bytes, 1 * 1024 * 1024)
    attempts.append((fallback_size, fallback_patterns, "fallback:docs-only"))

    return attempts


def get_repo_content(repo_url: str) -> tuple[str, str, str] | None:
    """Fetch repository content via gitingest with a fallback strategy."""
    last_error: Exception | None = None
    for max_file_size, include_patterns, label in _iter_ingest_attempts():
        try:
            summary, tree, content = gitingest.ingest(
                repo_url,
                max_file_size=max_file_size,
                include_patterns=include_patterns,
                token=settings.github_token,
            )
            return summary, tree, content
        except Exception as exc:  # pragma: no cover - best-effort network
            last_error = exc
            print(
                f"Error fetching repo {repo_url} ({label}, max_file_size={max_file_size}): {exc}"
            )

    print(f"Failed to fetch repo {repo_url} after retries: {last_error}")
    return None


# -------- Extraction helpers -------- #


def extract_readme(content: str) -> str:
    """Return README text if present (up to 8000 chars)."""
    match = re.search(
        r"(?:^|\n)(#{1,3}\s*)?(README(?:\.md)?)\n(.*?)(?=\n#{1,3}\s+|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group(3).strip()[:8000]


def extract_files(
    content: str, max_files: int, max_chars: int
) -> list[tuple[str, str]]:
    """Extract up to max_files sections with filename and preview (max_chars)."""
    file_pattern = r"\n(?:#{1,3}\s+)([^\n]+)\n(.*?)(?=\n#{1,3}\s+|\Z)"
    files = re.findall(file_pattern, content, re.DOTALL)

    skip_patterns: Iterable[str] = [
        r"\.lock$",
        r"\.min\.",
        r"\.bundle\.",
        r"\.map$",
        r"package-lock",
        r"yarn\.lock",
        r"pnpm-lock",
        r"\.git",
        r"node_modules",
        r"__pycache__",
        r"\.png$",
        r"\.jpg$",
        r"\.jpeg$",
        r"\.gif$",
        r"\.svg$",
        r"\.ico$",
        r"\.woff",
        r"\.ttf$",
        r"\.eot$",
    ]

    def should_skip(name: str) -> bool:
        return any(re.search(pattern, name, re.IGNORECASE) for pattern in skip_patterns)

    def priority(name: str) -> int:
        lower = name.lower()
        if lower.startswith("readme"):
            return 0
        if lower.endswith((".md", ".rst", ".txt")) and "doc" in lower:
            return 1
        if lower in ("setup.py", "pyproject.toml", "package.json", "cargo.toml"):
            return 2
        if lower.endswith((".py", ".js", ".ts", ".rs", ".go", ".java", ".cpp", ".c")):
            return 3
        if lower.endswith((".yaml", ".yml", ".toml", ".json", ".xml")):
            return 4
        return 5

    filtered = []
    for filename, body in files:
        name = filename.strip()
        if should_skip(name):
            continue
        filtered.append((name, body))

    filtered.sort(key=lambda item: priority(item[0]))
    filtered = filtered[:max_files]

    previews = []
    for name, body in filtered:
        preview = body.strip()[:max_chars]
        if preview:
            previews.append((name, preview))
    return previews


def build_context_blocks(tree: str, content: str) -> tuple[str, str, str]:
    """Return (readme_block, structure_block, files_block) with clear labels."""
    readme_text = extract_readme(content)
    structure_text = tree[:3000] if tree else ""
    files = extract_files(
        content,
        max_files=settings.max_files,
        max_chars=settings.max_file_preview_chars,
    )

    readme_block = readme_text if readme_text else "(README missing or empty)"

    file_chunks = [f"FILE: {name}\n{preview}" for name, preview in files]
    files_block = (
        "\n\n---\n\n".join(file_chunks)
        if file_chunks
        else "(No additional files captured)"
    )

    return readme_block, structure_text, files_block


# -------- LLM call -------- #


def call_ollama(prompt: str) -> str | None:
    """Call local Ollama model. Returns text or None on failure."""
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": settings.ollama_model_name,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.4,
            },
            timeout=settings.ollama_timeout,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:  # pragma: no cover - best-effort network
        print(f"Ollama error: {exc}")
    return None


# -------- Public API -------- #


def generate_summary(repo_url: str, repo_name: str) -> str:
    """Generate a natural summary without hardcoded keywords."""
    print("  ⏳ Fetching repository content...")
    result = get_repo_content(repo_url)
    if not result:
        return ""

    _, tree, content = result
    if not content:
        return ""

    print("  ⏳ Building context blocks...")
    readme_block, structure_block, files_block = build_context_blocks(tree, content)

    prompt_blocks = f"""
Repository: {repo_name}

[README]
{readme_block}

[STRUCTURE]
{structure_block}

[FILES]
{files_block}
"""

    if len(prompt_blocks) > settings.max_prompt_chars:
        print(f"  📏 Context {len(prompt_blocks)} chars too large; truncating...")
        prompt_blocks = (
            prompt_blocks[: settings.max_prompt_chars]
            + "\n[... truncated ...]"
        )

    prompt = f"""You are a technical writer writing a detailed summary for a developer knowledge base.

Write a 12-15 sentence summary of {repo_name}. Be as specific and concrete as possible.

Structure your response in clear sections:

**What & Why:** What is this project? (library, framework, tool, SDK, CLI, API, etc.) What problem does it solve?

**Core Features:** List 3-5 specific capabilities or features mentioned in the README/files. Be concrete, not vague.

**Use Case:** Who is the primary audience? What types of developers/teams use this?

**Tech Stack:** What are the key technologies, dependencies, or programming language(s)?

**Integration:** How is it used? (install as package, CLI tool, REST API, embed in code, etc.)

**Strengths:** What makes this unique or better than alternatives (if mentioned)?

Specificity over vagueness. Instead of "data tool" say "processes 1M+ events/sec" or "manages time-series with 99.9% uptime".
DO NOT mention installation steps or configuration details.
DO NOT add artificial padding. Use all 12-15 sentences to be informative.

{prompt_blocks}

Summary:"""

    print("  ⏳ Generating summary with LLM...")
    summary_text = call_ollama(prompt)
    if summary_text:
        return summary_text

    print("  ⚠️  Ollama not available; returning context preview.")
    fallback = f"README: {readme_block}\n\nSTRUCTURE: {structure_block[:800]}"
    return fallback
