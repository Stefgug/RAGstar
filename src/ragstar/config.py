"""Configuration for RAGstar.

Note on import-time config loading:
Configuration is loaded at module import time to fail fast if the config is
invalid or missing. This ensures the application cannot start with invalid
configuration. For applications requiring lazy config loading or better error
handling at startup, consider moving config loading to a FastAPI lifespan event.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import shutil

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from huggingface_hub import snapshot_download
import yaml


@dataclass(frozen=True)
class Settings:
    chroma_db_path: Path
    chroma_collection_name: str
    embedding_model: str
    embedding_local_only: bool
    gitingest_max_file_size_mb: int
    gitingest_include_patterns: str
    ollama_url: str
    ollama_pull_url: str
    ollama_model_name: str
    ollama_timeout: int
    max_prompt_chars: int
    max_files: int
    max_file_preview_chars: int
    github_token: str



def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration from the specified path.
    
    Note: The default config path is relative to the current working directory.
    In containerized environments, this is controlled by WORKDIR. For local
    development, run from the project root or set RAGSTAR_CONFIG_PATH to an
    absolute path.
    """
    if not path.exists():
        raise RuntimeError(
            "RAGstar YAML config not found. Set RAGSTAR_CONFIG_PATH or "
            "create a config file at the default path: ./ragstar.yaml"
        )
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:  # pragma: no cover - config parsing
        raise RuntimeError(f"Failed to load YAML config at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML config at {path} must be a mapping of keys.")
    return data


_CONFIG_PATH = Path(os.getenv("RAGSTAR_CONFIG_PATH", "./ragstar.yaml"))
_CONFIG_DATA = _load_yaml_config(_CONFIG_PATH)
_SETTINGS_DATA = _CONFIG_DATA.get("settings", {})
if _SETTINGS_DATA is None:
    _SETTINGS_DATA = {}
if not isinstance(_SETTINGS_DATA, dict):
    raise RuntimeError("'settings' section in YAML config must be a mapping.")


def _get_config_value(key: str, default: Any = None) -> Any:
    if key in _SETTINGS_DATA:
        return _SETTINGS_DATA[key]
    return _CONFIG_DATA.get(key, default)


def _read_str(env_name: str, key: str, default: str | None = None) -> str | None:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value
    value = _get_config_value(key, default)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _read_required_str(env_name: str, key: str) -> str:
    value = _read_str(env_name, key)
    if value is None or not value.strip():
        raise RuntimeError(
            f"Required configuration '{key}' is not set. Provide {env_name} "
            f"environment variable or set '{key}' in {_CONFIG_PATH}."
        )
    return value


def _derive_ollama_pull_url(generate_url: str) -> str:
    trimmed = generate_url.rstrip("/")
    if trimmed.endswith("/api/generate"):
        return trimmed[: -len("/api/generate")] + "/api/pull"
    return f"{trimmed}/api/pull"


def _read_int(env_name: str, key: str, default: int) -> int:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return int(env_value)
    value = _get_config_value(key, default)
    return int(value) if value is not None else default


def _read_bool(env_name: str, key: str, default: bool) -> bool:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    value = _get_config_value(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_include_patterns(env_name: str, key: str, default: str = "") -> str:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value
    value = _get_config_value(key, default)
    if value is None:
        return default
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value)
    return str(value)


_ollama_url = _read_required_str("RAGSTAR_OLLAMA_URL", "ollama_url")
settings = Settings(
    chroma_db_path=Path(_read_str("RAGSTAR_DB_PATH", "chroma_db_path", "./ragstar_db") or "./ragstar_db"),
    chroma_collection_name=_read_str("RAGSTAR_COLLECTION", "chroma_collection_name", "repositories")
    or "repositories",
    embedding_model=_read_str("RAGSTAR_EMBEDDING_MODEL", "embedding_model", "all-MiniLM-L6-v2")
    or "all-MiniLM-L6-v2",
    embedding_local_only=_read_bool("RAGSTAR_EMBEDDING_LOCAL_ONLY", "embedding_local_only", False),
    gitingest_max_file_size_mb=_read_int("RAGSTAR_GITINGEST_MAX_FILE_SIZE_MB", "gitingest_max_file_size_mb", 3),
    gitingest_include_patterns=_read_include_patterns(
        "RAGSTAR_GITINGEST_INCLUDE_PATTERNS",
        "gitingest_include_patterns",
        "",
    ),
    ollama_url=_ollama_url,
    ollama_pull_url=_read_str(
        "RAGSTAR_OLLAMA_PULL_URL",
        "ollama_pull_url",
        _derive_ollama_pull_url(_ollama_url),
    )
    or _derive_ollama_pull_url(_ollama_url),
    ollama_model_name=_read_str("RAGSTAR_OLLAMA_MODEL", "ollama_model_name", "mistral")
    or "mistral",
    ollama_timeout=_read_int("RAGSTAR_OLLAMA_TIMEOUT", "ollama_timeout", 180),
    max_prompt_chars=_read_int("RAGSTAR_MAX_PROMPT_CHARS", "max_prompt_chars", 120000),
    max_files=_read_int("RAGSTAR_MAX_FILES", "max_files", 30),
    max_file_preview_chars=_read_int("RAGSTAR_MAX_FILE_PREVIEW_CHARS", "max_file_preview_chars", 2000),
    github_token=_read_str("RAGSTAR_GITHUB_TOKEN", "github_token", "") or "",
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
        print("  You can now run build_index() to rebuild from scratch.")
    except Exception as exc:
        print(f"Error clearing database: {exc}")
