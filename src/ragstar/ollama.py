"""Shared Ollama client helpers."""

import logging

import requests

from .config import settings, OLLAMA_TIMEOUT, get_ollama_headers, get_ollama_verify

logger = logging.getLogger(__name__)


def pull_ollama_model(model_name: str | None = None) -> bool:
    """Ensure an Ollama model is available by pulling it if missing."""
    name = model_name or settings.ollama_model_name
    try:
        resp = requests.post(
            settings.ollama_pull_url,
            json={"name": name, "stream": False},
            headers=get_ollama_headers(),
            timeout=OLLAMA_TIMEOUT,
            verify=get_ollama_verify(),
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
            headers=get_ollama_headers(),
            timeout=OLLAMA_TIMEOUT,
            verify=get_ollama_verify(),
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
                    headers=get_ollama_headers(),
                    timeout=OLLAMA_TIMEOUT,
                    verify=get_ollama_verify(),
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
