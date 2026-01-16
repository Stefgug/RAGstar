"""Configuration for RAGstar."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from huggingface_hub import snapshot_download


REPOSITORIES: list[dict[str, str]] = [
    {"name": "awesome-copilot", "url": "https://github.com/github/awesome-copilot"},
    {"name": "LightRAG", "url": "https://github.com/HKUDS/LightRAG"},
    {"name": "txtai", "url": "https://github.com/neuml/txtai"},
    {"name": "github-local-actions", "url": "https://github.com/SanjulaGanepola/github-local-actions"},
    {"name": "python-mastery", "url": "https://github.com/dabeaz-course/python-mastery"},
    {"name": "ollama-docker", "url": "https://github.com/mythrantic/ollama-docker"},
    {"name": "RAG_Techniques", "url": "https://github.com/NirDiamant/RAG_Techniques"},
    {"name": "sam3", "url": "https://github.com/facebookresearch/sam3"},
    {"name": "karpathy", "url": "https://github.com/K-Dense-AI/karpathy"},
    {"name": "cs249r_book", "url": "https://github.com/harvard-edge/cs249r_book"},
]


@dataclass(frozen=True)
class Settings:
    chroma_db_path: Path
    chroma_collection_name: str
    embedding_model: str
    embedding_local_only: bool
    gitingest_max_file_size_mb: int
    gitingest_include_patterns: str
    ollama_model_name: str
    ollama_timeout: int
    max_prompt_chars: int
    max_files: int
    max_file_preview_chars: int
    github_token: str



def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings(
    chroma_db_path=Path(os.getenv("RAGSTAR_DB_PATH", "./ragstar_db")),
    chroma_collection_name=os.getenv("RAGSTAR_COLLECTION", "repositories"),
    embedding_model=os.getenv("RAGSTAR_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    embedding_local_only=_env_bool("RAGSTAR_EMBEDDING_LOCAL_ONLY", False),
    gitingest_max_file_size_mb=int(os.getenv("RAGSTAR_GITINGEST_MAX_FILE_SIZE_MB", "3")),
    gitingest_include_patterns=os.getenv("RAGSTAR_GITINGEST_INCLUDE_PATTERNS", ""),
    ollama_model_name=os.getenv("RAGSTAR_OLLAMA_MODEL", "mistral"),
    ollama_timeout=int(os.getenv("RAGSTAR_OLLAMA_TIMEOUT", "180")),
    max_prompt_chars=int(os.getenv("RAGSTAR_MAX_PROMPT_CHARS", "120000")),
    max_files=int(os.getenv("RAGSTAR_MAX_FILES", "30")),
    max_file_preview_chars=int(os.getenv("RAGSTAR_MAX_FILE_PREVIEW_CHARS", "2000")),
    github_token=os.getenv("GITHUB_TOKEN", ""),
)


def get_collection():
    client = PersistentClient(path=str(settings.chroma_db_path))

    if settings.embedding_local_only:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # Prefer a local cached copy of the HF model when available to avoid
    # repeated HEAD requests to the Hugging Face hub. If a local snapshot
    # exists, use its filesystem path; otherwise fall back to the model id
    # which triggers a download if necessary.
    model_source = settings.embedding_model
    model_path = Path(model_source)
    if model_path.exists():
        model_source = str(model_path)
        print(f"Using local embedding model path: {model_source}")
    else:
        try:
            local_path = snapshot_download(
                repo_id=settings.embedding_model,
                local_files_only=True,
            )
            model_source = local_path
            print(f"Using locally cached embedding model at {local_path}")
        except Exception:
            if settings.embedding_local_only:
                raise RuntimeError(
                    "Embedding model not found in local cache. "
                    "Prefetch it with snapshot_download(...) or set "
                    "RAGSTAR_EMBEDDING_MODEL to a local path."
                )
            print(
                f"Embedding model '{settings.embedding_model}' not found in local cache; "
                "will download from Hugging Face if required."
            )

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=model_source
    )

    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=embedding_fn,
    )


def clear_database() -> None:
    db_path = Path(settings.chroma_db_path)

    if not db_path.exists():
        print(f"Database at {db_path} doesn't exist yet.")
        return

    try:
        shutil.rmtree(db_path)
        print(f"✓ Cleared database at {db_path}")
        print("  You can now run 'ragstar build' to rebuild from scratch.")
    except Exception as exc:
        print(f"Error clearing database: {exc}")
