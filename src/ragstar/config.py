"""Configuration for RAGstar."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import shutil
import logging

from chromadb import PersistentClient
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from huggingface_hub import snapshot_download
import yaml

# Module logger - configuration should be done at application level
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    ollama_pull_url: str
    ollama_model_name: str
    github_token: str
    admin_token: str


# Hardcoded defaults (simple app, rarely changed)
CHROMA_DB_PATH = Path("./ragstar_db")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GITINGEST_MAX_FILE_SIZE_MB = 3
OLLAMA_TIMEOUT = 180
CHROMA_COLLECTION_NAME = "repositories"



def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration from the specified path."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:  # pragma: no cover - config parsing
        raise RuntimeError(f"Failed to load YAML config at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML config at {path} must be a mapping of keys.")
    return data


_CONFIG_PATH = Path(os.getenv("RAGSTAR_CONFIG_PATH", "./ragstar.yaml"))
_RAW_CONFIG = _load_yaml_config(_CONFIG_PATH)
_SETTINGS = _RAW_CONFIG.get("settings", {}) if isinstance(_RAW_CONFIG.get("settings"), dict) else {}
_CONFIG_DATA = {**_RAW_CONFIG, **_SETTINGS}


def _read_value(env_name: str, key: str, default: Any = None) -> Any:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value
    return _CONFIG_DATA.get(key, default)


def _read_required_str(env_name: str, key: str) -> str:
    value = _read_value(env_name, key)
    if value is None or not str(value).strip():
        raise RuntimeError(
            f"Required configuration '{key}' is not set. Provide {env_name} "
            f"environment variable or set '{key}' in {_CONFIG_PATH}."
        )
    return str(value).strip()


def _derive_ollama_pull_url(generate_url: str) -> str:
    trimmed = generate_url.rstrip("/")
    if trimmed.endswith("/api/generate"):
        return trimmed[: -len("/api/generate")] + "/api/pull"
    return f"{trimmed}/api/pull"


_ollama_url = _read_required_str("RAGSTAR_OLLAMA_URL", "ollama_url")
settings = Settings(
    ollama_url=_ollama_url,
    ollama_pull_url=str(
        _read_value("RAGSTAR_OLLAMA_PULL_URL", "ollama_pull_url", _derive_ollama_pull_url(_ollama_url))
    ),
    ollama_model_name=str(_read_value("RAGSTAR_OLLAMA_MODEL", "ollama_model_name", "mistral")),
    github_token=str(_read_value("RAGSTAR_GITHUB_TOKEN", "github_token", "")),
    admin_token=str(_read_value("RAGSTAR_ADMIN_TOKEN", "admin_token", "")),
)


def _resolve_embedding_model_source() -> str:
    model_path = Path(EMBEDDING_MODEL)
    if model_path.exists():
        logger.info(f"Using local embedding model path: {model_path}")
        return str(model_path)

    try:
        local_path = snapshot_download(
            repo_id=EMBEDDING_MODEL,
            local_files_only=True,
        )
        logger.info(f"Using locally cached embedding model at {local_path}")
        return local_path
    except Exception:
        logger.info(
            f"Embedding model '{EMBEDDING_MODEL}' not found in local cache; "
            "downloading from Hugging Face."
        )

    return snapshot_download(
        repo_id=EMBEDDING_MODEL,
        local_files_only=False,
    )


def get_collection():
    client = PersistentClient(path=str(CHROMA_DB_PATH))

    model_source = _resolve_embedding_model_source()

    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=model_source)

    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=embedding_fn,
    )


def clear_database() -> bool:
    db_path = Path(CHROMA_DB_PATH)

    try:
        client = PersistentClient(path=str(db_path))
        try:
            client.delete_collection(name=CHROMA_COLLECTION_NAME)
            logger.info(f"Deleted collection '{CHROMA_COLLECTION_NAME}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to delete collection '{CHROMA_COLLECTION_NAME}': {exc}")
    except Exception as exc:
        logger.warning(f"Failed to create Chroma client for reset: {exc}")

    if not db_path.exists():
        logger.info(f"Database at {db_path} doesn't exist yet.")
        return True

    try:
        for child in db_path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        logger.info(f"Cleared database contents at {db_path}")
        return True
    except Exception as exc:
        logger.error(f"Error clearing database contents: {exc}")
        return False
