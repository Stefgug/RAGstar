"""
Repository Summarizer - Generates concise summaries of GitHub repositories using local LLM
"""

import re
import requests
import gitingest


def get_repo_content(repo_url: str) -> tuple[str, str, str]:
    """
    Fetch repository content using gitingest.

    Returns:
        Tuple of (summary, tree, content) from gitingest
    """
    try:
        summary, tree, content = gitingest.ingest(repo_url)
        return summary, tree, content
    except Exception as e:
        print(f"Error fetching repo {repo_url}: {e}")
        return "", "", ""


def extract_key_sections(content: str) -> str:
    """
    Extract key sections from repository content.
    Prioritizes README and other important documentation.
    """
    sections = []

    # Look for README section
    readme_match = re.search(r'(?:^|\n)(#+\s*)?README(?:\.md)?[\n\r]+(.*?)(?=\n#+\s|\Z)', content, re.IGNORECASE | re.DOTALL)
    if readme_match:
        readme_content = readme_match.group(2)
        sections.append(f"README:\n{readme_content}")

    # Look for package.json or pyproject.toml
    if "package.json" in content:
        pj_match = re.search(r'package\.json[\n\r]+(.*?)(?=\n[A-Z]|\Z)', content, re.DOTALL)
        if pj_match:
            sections.append(f"Project Config:\n{pj_match.group(1)[:2000]}")

    if "pyproject.toml" in content:
        pp_match = re.search(r'pyproject\.toml[\n\r]+(.*?)(?=\n[A-Z]|\Z)', content, re.DOTALL)
        if pp_match:
            sections.append(f"Project Config:\n{pp_match.group(1)[:2000]}")

    # If no README found, use beginning of content
    if not sections:
        sections.append(content[:1500])

    return "\n\n".join(sections)


def call_ollama(prompt: str) -> str:
    """
    Call local Ollama LLM to generate summary.

    Requires: ollama running locally with a model installed
    Install: https://ollama.ai
    Run: ollama run mistral (or other model)
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,
            },
            timeout=60
        )

        if response.status_code == 200:
            return response.json()["response"].strip()
        else:
            return None
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        print(f"Ollama error: {e}")
        return None


def generate_summary(repo_url: str, repo_name: str) -> str:
    """
    Generate a natural, human-readable summary of a repository.

    Uses Ollama with local LLM for high-quality summaries.

    Args:
        repo_url: GitHub repository URL
        repo_name: Repository name for context

    Returns:
        A natural language summary of the repository
    """
    print(f"  ⏳ Fetching repository content...")
    summary, tree, content = get_repo_content(repo_url)

    if not content:
        return f"Could not fetch {repo_name}"

    print(f"  ⏳ Extracting key sections...")
    key_content = extract_key_sections(content)

    # Try Ollama first (high quality)
    print(f"  ⏳ Generating summary with LLM...")
    prompt = f"""Based on this repository information, write a concise 4 to 10 sentences summary describing what this project does, its main purpose, and key features:

Repository: {repo_name}

{key_content}

Summary:"""

    summary_text = call_ollama(prompt)

    if summary_text:
        return summary_text

    # Fallback: return formatted key sections if Ollama unavailable
    print(f"  ⚠️  Ollama not available (ensure 'ollama serve' is running)")
    print(f"     Using extracted content instead...\n")
    return f"{repo_name}\n\n{key_content}"


if __name__ == "__main__":
    # Test the summarizer
    test_url = "https://github.com/HKUDS/LightRAG"
    print(f"Summarizing {test_url}...\n")
    summary = generate_summary(test_url, test_url.split("/")[-1])
    print(f"Generated Summary:\n{summary}")
