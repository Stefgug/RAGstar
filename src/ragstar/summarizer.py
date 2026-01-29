"""Repository summarization using local Ollama."""

import logging

import requests
import gitingest

from .config import (
    settings,
    GITINGEST_MAX_FILE_SIZE_MB,
    GITINGEST_INCLUDE_PATTERNS,
    MAX_FILE_PREVIEW_CHARS,
    MAX_FILES,
    MAX_PROMPT_CHARS,
    OLLAMA_TIMEOUT,
)

logger = logging.getLogger(__name__)


def get_repo_content(repo_url: str) -> tuple[str, str, str] | None:
    """Fetch repository content via gitingest with a fallback strategy."""
    max_size_bytes = max(1, GITINGEST_MAX_FILE_SIZE_MB) * 1024 * 1024
    include_patterns = GITINGEST_INCLUDE_PATTERNS.strip() or None

    try:
        return gitingest.ingest(
            repo_url,
            max_file_size=max_size_bytes,
            include_patterns=include_patterns,
            token=settings.github_token,
        )
    except Exception as exc:  # pragma: no cover - best-effort network
        logger.debug(f"Primary ingest failed for {repo_url}: {exc}")

    fallback_patterns = {"**/README*", "**/*.md", "**/*.rst", "**/*.txt"}
    try:
        return gitingest.ingest(
            repo_url,
            max_file_size=min(max_size_bytes, 1 * 1024 * 1024),
            include_patterns=fallback_patterns,
            token=settings.github_token,
        )
    except Exception as exc:  # pragma: no cover - best-effort network
        logger.warning(f"Failed to fetch {repo_url}: {exc}")
        return None


def _split_by_file(content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("FILE:"):
            if current_name is not None:
                sections.append((current_name, "\n".join(current_lines).strip("\n")))
            current_name = line[len("FILE:") :].strip()
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        sections.append((current_name, "\n".join(current_lines).strip("\n")))

    return sections


def _extract_readme(sections: list[tuple[str, str]]) -> str:
    for name, body in sections:
        base = name.split("/")[-1].split("\\")[-1].lower()
        if "readme" in base:
            return body.strip()[:8000]
    return ""


def _extract_root_docs(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for name, body in sections:
        if "/" in name or "\\" in name:
            continue
        lower = name.lower()
        if not lower.endswith((".toml", ".txt")):
            continue
        preview = body.strip()[: MAX_FILE_PREVIEW_CHARS]
        if preview:
            docs.append((name, preview))
    return docs[: MAX_FILES]


def _build_context(content: str) -> tuple[str, str]:
    sections = _split_by_file(content)
    readme = _extract_readme(sections) or "(README missing or empty)"
    docs = _extract_root_docs(sections)
    docs_block = "\n\n---\n\n".join([f"FILE: {name}\n{preview}" for name, preview in docs])
    if not docs_block:
        docs_block = "(No root .toml/.txt files captured)"
    return readme, docs_block


# -------- LLM call -------- #


def pull_ollama_model(model_name: str | None = None) -> bool:
    """Ensure an Ollama model is available by pulling it if missing."""
    name = model_name or settings.ollama_model_name
    try:
        resp = requests.post(
            settings.ollama_pull_url,
            json={"name": name, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            return True
        logger.error(f"Ollama pull failed ({resp.status_code}): {resp.text}")
    except Exception as exc:  # pragma: no cover - best-effort network
        logger.error(f"Ollama pull error: {exc}")
    return False


def call_ollama(prompt: str) -> str | None:
    """Call local Ollama model. Returns text or None on failure."""
    payload = {
        "model": settings.ollama_model_name,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.4,
    }
    
    try:
        resp = requests.post(
            settings.ollama_url,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        
        # If model not found, try to pull it once
        if resp.status_code == 404:
            logger.info(f"Model {settings.ollama_model_name} not found, attempting to pull")
            if pull_ollama_model(settings.ollama_model_name):
                # Retry the request after successful pull
                retry_resp = requests.post(
                    settings.ollama_url,
                    json=payload,
                    timeout=OLLAMA_TIMEOUT,
                )
                if retry_resp.status_code == 200:
                    return retry_resp.json().get("response", "").strip()
                logger.error(f"Ollama retry failed ({retry_resp.status_code})")
            else:
                logger.error(f"Failed to pull model {settings.ollama_model_name}")
        else:
            logger.error(f"Ollama request failed ({resp.status_code})")
            
    except requests.exceptions.ConnectionError:
        logger.warning("Cannot connect to Ollama service")
        return None
    except Exception as exc:  # pragma: no cover - best-effort network
        logger.error(f"Ollama error: {exc}")
    
    return None


# -------- Public API -------- #


def generate_summary(repo_url: str, repo_name: str) -> str:
    """Generate a summary based on README and root .toml/.txt files only."""
    logger.debug(f"Fetching repository content for {repo_name}")
    result = get_repo_content(repo_url)
    if not result:
        return ""

    _, _tree, content = result
    if not content:
        return ""

    logger.debug(f"Building context blocks for {repo_name}")
    readme_block, docs_block = _build_context(content)

    prompt_blocks = f"""
Repository: {repo_name}

[README]
{readme_block}

[ROOT_DOCS]
{docs_block}
"""

    if len(prompt_blocks) > MAX_PROMPT_CHARS:
        logger.debug(f"Context for {repo_name} is {len(prompt_blocks)} chars, truncating")
        prompt_blocks = (
            prompt_blocks[: MAX_PROMPT_CHARS]
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
DO NOT INCLUDE ANY MARKDOWN FORMATTING, URLS, OR HTML TAGS IN YOUR RESPONSE. ONLY HUMAN READABLE TEXT.
DO NOT add artificial padding. Use all 3-10 sentences to be informative.
Do not mention if no root .toml/.txt files were found.

{prompt_blocks}

Summary:"""

    logger.debug(f"Generating summary with LLM for {repo_name}")
    summary_text = call_ollama(prompt)
    if summary_text:
        return summary_text

    logger.warning(f"Ollama not available for {repo_name}, returning context preview")
    fallback = f"README: {readme_block}\n\nROOT_DOCS: {docs_block[:800]}"
    return fallback
