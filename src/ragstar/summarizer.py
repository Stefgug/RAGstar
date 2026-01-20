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


def _clean_filename(name: str) -> str:
    cleaned = name.strip().strip("`")
    cleaned = re.sub(r"\s+\(.*\)$", "", cleaned)
    cleaned = re.sub(r"^(file|path|filename)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[-=]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[-=]+$", "", cleaned)
    return cleaned


def _parse_file_sections(content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []

    header_pattern = re.compile(
        r"(?:^|\n)(?:#{1,6}\s+|(?:file|path|filename)\s*:\s+)([^\n]+)\n",
        re.IGNORECASE,
    )
    matches = list(header_pattern.finditer(content))
    if matches:
        for idx, match in enumerate(matches):
            name = _clean_filename(match.group(1))
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            body = content[start:end].strip("\n")
            sections.append((name, body))
        return sections

    sep_pattern = re.compile(
        r"(?:^|\n)(?:=+|-+)\n([^\n]+)\n(?:=+|-+)\n",
        re.IGNORECASE,
    )
    matches = list(sep_pattern.finditer(content))
    if matches:
        for idx, match in enumerate(matches):
            name = _clean_filename(match.group(1))
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            body = content[start:end].strip("\n")
            sections.append((name, body))

    if sections:
        return sections

    single_line_sep = re.compile(
        r"(?:^|\n)(?:=+|-+)\s*([^\n]+?)\s*(?:=+|-+)(?:\n|$)",
        re.IGNORECASE,
    )
    matches = list(single_line_sep.finditer(content))
    if matches:
        for idx, match in enumerate(matches):
            name = _clean_filename(match.group(1))
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            body = content[start:end].strip("\n")
            sections.append((name, body))

    return sections


def extract_readme(content: str) -> str:
    """Return README text if present (up to 8000 chars)."""
    sections = _parse_file_sections(content)
    if sections:
        for name, body in sections:
            base = name.split("/")[-1].split("\\")[-1].lower()
            if base.startswith("readme"):
                return body.strip()[:8000]
        for name, body in sections:
            base = name.split("/")[-1].split("\\")[-1].lower()
            if "readme" in base:
                return body.strip()[:8000]

    match = re.search(
        r"(?:^|\n)(?:#{1,6}\s+|FILE:\s+)?(README(?:\.(?:md|rst|txt))?)\n(.*?)(?=\n(?:#{1,6}\s+|FILE:\s+)|\Z)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return match.group(2).strip()[:8000]


def extract_root_docs(
    content: str, max_files: int, max_chars: int
) -> list[tuple[str, str]]:
    """Extract root-level .toml or .txt file sections with previews."""
    sections = _parse_file_sections(content)

    def is_root_file(name: str) -> bool:
        return "/" not in name and "\\" not in name

    def wanted(name: str) -> bool:
        lower = name.lower()
        return lower.endswith((".toml", ".txt"))

    filtered: list[tuple[str, str]] = []
    if sections:
        for filename, body in sections:
            name = _clean_filename(filename)
            if not is_root_file(name):
                continue
            if not wanted(name):
                continue
            filtered.append((name, body))
    else:
        file_pattern = r"\n(?:#{1,6}\s+)([^\n]+)\n(.*?)(?=\n#{1,6}\s+|\Z)"
        files = re.findall(file_pattern, content, re.DOTALL)
        for filename, body in files:
            name = _clean_filename(filename)
            if not is_root_file(name):
                continue
            if not wanted(name):
                continue
            filtered.append((name, body))

    filtered = filtered[:max_files]

    previews = []
    for name, body in filtered:
        preview = body.strip()[:max_chars]
        if preview:
            previews.append((name, preview))
    return previews


def build_context_blocks(content: str) -> tuple[str, str]:
    """Return (readme_block, root_docs_block) with clear labels."""
    readme_text = extract_readme(content)
    root_docs = extract_root_docs(
        content,
        max_files=settings.max_files,
        max_chars=settings.max_file_preview_chars,
    )

    readme_block = readme_text if readme_text else "(README missing or empty)"

    doc_chunks = [f"FILE: {name}\n{preview}" for name, preview in root_docs]
    docs_block = (
        "\n\n---\n\n".join(doc_chunks)
        if doc_chunks
        else "(No root .toml/.txt files captured)"
    )

    return readme_block, docs_block


# -------- LLM call -------- #


def pull_ollama_model(model_name: str | None = None) -> bool:
    """Ensure an Ollama model is available by pulling it if missing."""
    name = model_name or settings.ollama_model_name
    try:
        resp = requests.post(
            settings.ollama_pull_url,
            json={"name": name, "stream": False},
            timeout=settings.ollama_timeout,
        )
        if resp.status_code == 200:
            return True
        print(f"Ollama pull failed ({resp.status_code}): {resp.text}")
    except Exception as exc:  # pragma: no cover - best-effort network
        print(f"Ollama pull error: {exc}")
    return False


def call_ollama(prompt: str) -> str | None:
    """Call local Ollama model. Returns text or None on failure."""
    try:
        resp = requests.post(
            settings.ollama_url,
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
        if resp.status_code == 404:
            if pull_ollama_model(settings.ollama_model_name):
                retry = requests.post(
                    settings.ollama_url,
                    json={
                        "model": settings.ollama_model_name,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.4,
                    },
                    timeout=settings.ollama_timeout,
                )
                if retry.status_code == 200:
                    return retry.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:  # pragma: no cover - best-effort network
        print(f"Ollama error: {exc}")
    return None


# -------- Public API -------- #


def generate_summary(repo_url: str, repo_name: str) -> str:
    """Generate a summary based on README and root .toml/.txt files only."""
    print("  ⏳ Fetching repository content...")
    result = get_repo_content(repo_url)
    if not result:
        return ""

    _, _tree, content = result
    if not content:
        return ""

    print("  ⏳ Building context blocks...")
    readme_block, docs_block = build_context_blocks(content)

    prompt_blocks = f"""
Repository: {repo_name}

[README]
{readme_block}

[ROOT_DOCS]
{docs_block}
"""

    if len(prompt_blocks) > settings.max_prompt_chars:
        print(f"  📏 Context {len(prompt_blocks)} chars too large; truncating...")
        prompt_blocks = (
            prompt_blocks[: settings.max_prompt_chars]
            + "\n[... truncated ...]"
        )

    prompt = f"""You are a technical writer writing a detailed summary for a developer knowledge base.

Write a 3-10 sentence summary of {repo_name}. Be as specific and concrete as possible.

Structure your response in clear sections:

**What & Why:** What is this project? (library, framework, tool, SDK, CLI, API, etc.) What problem does it solve?

**Core Features:** List 3-5 specific capabilities or features mentioned in the README/files. Be concrete, not vague.

**Use Case:** Who is the primary audience? What types of developers/teams use this?

**Tech Stack:** What are the key technologies, dependencies, or programming language(s)?

**Integration:** How is it used? (install as package, CLI tool, REST API, embed in code, etc.)

**Strengths:** What makes this unique or better than alternatives (if mentioned)?

Specificity over vagueness. Instead of "data tool" say "processes 1M+ events/sec" or "manages time-series with 99.9% uptime".
Only use information from the README and root-level .toml/.txt files shown below.
DO NOT mention installation steps or configuration details.
DO NOT INCLUDE ANY MARKDOWN FORMATTING IN YOUR RESPONSE OR URL OR HTTP BALISE. ONLY HUMAN READABLE TEXT.
DO NOT add artificial padding. Use all 3-10 sentences to be informative.
NO NEED TO SPECIFY No root .toml/.txt files captured

{prompt_blocks}

Summary:"""

    print("  ⏳ Generating summary with LLM...")
    summary_text = call_ollama(prompt)
    if summary_text:
        return summary_text

    print("  ⚠️  Ollama not available; returning context preview.")
    fallback = f"README: {readme_block}\n\nROOT_DOCS: {docs_block[:800]}"
    return fallback
