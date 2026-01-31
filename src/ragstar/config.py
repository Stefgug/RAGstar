"""Configuration for RAGstar."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import shutil
import logging
import tempfile

import requests
import certifi
from chromadb import PersistentClient
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
import yaml

# Module logger - configuration should be done at application level
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    ollama_pull_url: str
    ollama_api_key: str
    ollama_model_name: str
    ollama_embedding_model_name: str
    github_token: str
    admin_token: str


# Hardcoded defaults (simple app, rarely changed)
OLLAMA_EMBEDDING_MODEL_DEFAULT = "nomic-embed-text"
GITINGEST_MAX_FILE_SIZE_MB = 3
OLLAMA_TIMEOUT = 180
CHROMA_COLLECTION_NAME = "repositories"


def _ensure_db_writable(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - best-effort filesystem
        logger.warning(f"Failed to create database path {path}: {exc}")
        return

    def _chmod_writable(target: Path) -> None:
        if os.access(target, os.W_OK):
            return
        try:
            target.chmod(target.stat().st_mode | 0o200)
        except PermissionError as exc:  # pragma: no cover - best-effort filesystem
            if target.name == "lost+found":
                logger.debug(f"Skipping permission update for {target}: {exc}")
            else:
                logger.debug(f"Permission update skipped for {target}: {exc}")
        except Exception as exc:  # pragma: no cover - best-effort filesystem
            logger.warning(f"Failed to set write permission on {target}: {exc}")

    _chmod_writable(path)
    for child in path.glob("**/*"):
        _chmod_writable(child)



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


def _read_db_path() -> Path:
    value = _read_value("RAGSTAR_DB_PATH", "chroma_db_path", "./ragstar_db")
    return Path(str(value)).expanduser()


CHROMA_DB_PATH = _read_db_path()


def _derive_ollama_pull_url(generate_url: str) -> str:
    trimmed = generate_url.rstrip("/")
    if trimmed.endswith("/api/generate"):
        return trimmed[: -len("/api/generate")] + "/api/pull"
    return f"{trimmed}/api/pull"


def _derive_ollama_embeddings_url(generate_url: str) -> str:
    trimmed = generate_url.rstrip("/")
    if trimmed.endswith("/api/generate"):
        return trimmed[: -len("/api/generate")] + "/api/embeddings"
    if trimmed.endswith("/api/embeddings"):
        return trimmed
    return f"{trimmed}/api/embeddings"


_ollama_url = _read_required_str("RAGSTAR_OLLAMA_URL", "ollama_url")
settings = Settings(
    ollama_url=_ollama_url,
    ollama_pull_url=str(
        _read_value("RAGSTAR_OLLAMA_PULL_URL", "ollama_pull_url", _derive_ollama_pull_url(_ollama_url))
    ),
    ollama_api_key=str(_read_value("RAGSTAR_OLLAMA_API_KEY", "ollama_api_key", "")),
    ollama_model_name=str(_read_value("RAGSTAR_OLLAMA_MODEL", "ollama_model_name", "mistral")),
    ollama_embedding_model_name=str(
        _read_value(
            "RAGSTAR_OLLAMA_EMBED_MODEL",
            "ollama_embedding_model_name",
            OLLAMA_EMBEDDING_MODEL_DEFAULT,
        )
    ),
    github_token=str(_read_value("RAGSTAR_GITHUB_TOKEN", "github_token", "")),
    admin_token=str(_read_value("RAGSTAR_ADMIN_TOKEN", "admin_token", "")),
)


_ollama_verify_bundle: str | None = None


def get_ollama_verify() -> str | bool:
    global _ollama_verify_bundle
    ca_path = os.getenv("OLLAMA_CA_CERT", "").strip()
    if not ca_path:
        return True
    if _ollama_verify_bundle:
        return _ollama_verify_bundle
    try:
        with open(certifi.where(), "rb") as base_handle, open(ca_path, "rb") as ca_handle:
            bundle = base_handle.read() + b"\n" + ca_handle.read()
        tmp = tempfile.NamedTemporaryFile(prefix="ollama-ca-", suffix=".crt", delete=False)
        tmp.write(bundle)
        tmp.flush()
        tmp.close()
        _ollama_verify_bundle = tmp.name
        return _ollama_verify_bundle
    except Exception as exc:  # pragma: no cover - best-effort TLS setup
        logger.warning(f"Failed to build Ollama CA bundle: {exc}")
        return ca_path


def get_ollama_headers() -> dict[str, str] | None:
    api_key = settings.ollama_api_key.strip()
    if not api_key:
        return None
    return {"X-API-Key": api_key}


class OllamaEmbeddingFunction(EmbeddingFunction):
    def __init__(self, embeddings_url: str, model_name: str, timeout: int, headers: dict[str, str] | None) -> None:
        self.embeddings_url = embeddings_url
        self.model_name = model_name
        self.timeout = timeout
        self.headers = headers
        self._name = f"ollama:{self.model_name}"

    def name(self) -> str:
        return self._name

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []

        embeddings: list[list[float]] = []
        for text in input:
            try:
                resp = requests.post(
                    self.embeddings_url,
                    json={"model": self.model_name, "prompt": text},
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=get_ollama_verify(),
                )
            except requests.exceptions.ConnectionError as exc:
                raise RuntimeError("Cannot connect to Ollama embeddings service") from exc
            except Exception as exc:  # pragma: no cover - network error
                raise RuntimeError(f"Ollama embeddings request failed: {exc}") from exc

            if resp.status_code != 200:
                raise RuntimeError(
                    "Ollama embeddings request failed "
                    f"({resp.status_code}): {resp.text}"
                )

            payload = resp.json()
            embedding = payload.get("embedding")
            if not embedding:
                raise RuntimeError("Ollama embeddings response missing 'embedding'")

            embeddings.append(embedding)

        return embeddings


def get_collection():
    _ensure_db_writable(CHROMA_DB_PATH)
    client = PersistentClient(path=str(CHROMA_DB_PATH))

    embeddings_url = _derive_ollama_embeddings_url(settings.ollama_url)
    embedding_fn = OllamaEmbeddingFunction(
        embeddings_url=embeddings_url,
        model_name=settings.ollama_embedding_model_name,
        timeout=OLLAMA_TIMEOUT,
        headers=get_ollama_headers(),
    )

    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=embedding_fn,
    )


def clear_database() -> bool:
    db_path = Path(CHROMA_DB_PATH)

    _ensure_db_writable(db_path)

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
        _ensure_db_writable(db_path)
        return True
    except Exception as exc:
        logger.error(f"Error clearing database contents: {exc}")
        return False
