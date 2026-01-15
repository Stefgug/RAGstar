"""
Repository Summarizer - clean rewrite
Generates human-readable summaries using local Ollama.
"""

import re
import requests
import gitingest


# -------- Ingest helpers -------- #


def get_repo_content(repo_url: str) -> tuple[str, str, str]:
    """Fetch repository content via gitingest."""
    try:
        summary, tree, content = gitingest.ingest(repo_url)
        return summary, tree, content
    except Exception as exc:
        print(f"Error fetching repo {repo_url}: {exc}")
        return "", "", ""


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
    content: str, max_files: int = 30, max_chars: int = 2000
) -> list[tuple[str, str]]:
    """Extract up to max_files sections with filename and preview (max_chars)."""
    file_pattern = r"\n(?:#{1,3}\s+)([^\n]+)\n(.*?)(?=\n#{1,3}\s+|\Z)"
    files = re.findall(file_pattern, content, re.DOTALL)

    skip_patterns = [
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
    files = extract_files(content)

    # README block
    readme_block = readme_text if readme_text else "(README missing or empty)"

    # Files block
    file_chunks = []
    for name, preview in files:
        file_chunks.append(f"FILE: {name}\n{preview}")
    files_block = (
        "\n\n---\n\n".join(file_chunks)
        if file_chunks
        else "(No additional files captured)"
    )

    return readme_block, structure_text, files_block


# -------- LLM call -------- #


def call_ollama(prompt: str) -> str:
    """Call local Ollama model. Returns text or None on failure."""
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.4,
            },
            timeout=90,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:
        print(f"Ollama error: {exc}")
    return None


# -------- Public API -------- #


def generate_summary(repo_url: str, repo_name: str) -> str:
    """Generate a natural summary without hardcoded keywords."""
    print("  ⏳ Fetching repository content...")
    summary, tree, content = get_repo_content(repo_url)
    if not content:
        return f"Could not fetch {repo_name}"

    print("  ⏳ Building context blocks...")
    readme_block, structure_block, files_block = build_context_blocks(tree, content)

    # Assemble prompt blocks
    prompt_blocks = f"""
Repository: {repo_name}

[README]
{readme_block}

[STRUCTURE]
{structure_block}

[FILES]
{files_block}
"""

    # Control overall size
    if len(prompt_blocks) > 120000:
        print(f"  📏 Context {len(prompt_blocks)} chars too large; truncating...")
        prompt_blocks = prompt_blocks[:120000] + "\n[... truncated ...]"

    # Improved prompt: focus on specificity and structure
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
