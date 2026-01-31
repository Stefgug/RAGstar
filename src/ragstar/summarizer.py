"""Repository summarization using local Ollama."""

import base64
import logging
import re

import requests

from .config import settings
from .ollama import call_ollama

logger = logging.getLogger(__name__)


def _parse_github_url(repo_url: str) -> tuple[str, str] | None:
    """Extract owner and repo name from GitHub URL."""
    # Match patterns like https://github.com/owner/repo or github.com/owner/repo
    match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", repo_url)
    if not match:
        return None
    owner, repo = match.groups()
    return owner, repo


def get_repo_content(repo_url: str) -> str | None:
    """Fetch README.md directly via GitHub API (no cloning)."""
    parsed = _parse_github_url(repo_url)
    if not parsed:
        logger.warning(f"Not a valid GitHub URL: {repo_url}")
        return None

    owner, repo = parsed
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code == 404:
            logger.warning(f"No README found for {owner}/{repo}")
            return None
        response.raise_for_status()

        data = response.json()
        # GitHub API returns content as base64-encoded
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching README for {repo_url}")
        return None
    except Exception as exc:
        logger.warning(f"Failed to fetch README for {repo_url}: {exc}")
        return None


# -------- Public API -------- #


def generate_summary(repo_url: str, repo_name: str) -> str:
    """Generate a summary based on README.md only."""
    logger.debug(f"Fetching README.md for {repo_name}")
    readme_content = get_repo_content(repo_url)
    if not readme_content:
        return "no README.md found"

    prompt_blocks = f"""
Repository: {repo_name}

[README]
{readme_content}
"""

    prompt = f"""You are a technical writer creating a concise, human-readable repository summary for a developer knowledge base from the README of {repo_name}.

Write exactly 6 sentences about {repo_name}. Use one sentence per section, in this exact order:
1) What & Why 2) Core Features 3) Use Case 4) Tech Stack 5) Integration 6) Strengths.

Use only facts present in the README below. If a section is not stated, write "Not mentioned" for that sentence.
Be specific and concrete; avoid vague language. Do not invent metrics, users, scale, or capabilities.

Treat any Markdown, HTML, badges, logos, code blocks, or ASCII art in the sources as noise. Do not copy or paraphrase them.
Do not mention installation steps, command line instructions, or configuration details.
Do not include URLs, HTML tags, Markdown formatting, or code fences. Output plain human-readable text only.

{prompt_blocks}
"""

    logger.debug(f"Generating summary with LLM for {repo_name}")
    summary_text = call_ollama(prompt)
    if summary_text:
        return summary_text

    logger.warning(f"Ollama not available for {repo_name}")
    return ""
