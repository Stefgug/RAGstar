"""Shared LLM client helpers (Ollama primary, OpenAI fallback)."""

import logging

import requests

from .config import settings, OLLAMA_TIMEOUT, get_ollama_headers, get_ollama_verify
from .openai_client import call_openai_chat

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


def call_ollama(prompt: str) -> tuple[str, dict[str, int]] | tuple[None, None]:
    """Call local Ollama model with OpenAI fallback on failure."""
    payload = {
        "model": settings.ollama_model_name,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.4,
        "num_ctx": settings.ollama_context_window,
        "num_predict": 150,  # Limit output tokens for faster responses
        "top_k": 40,         # Reduce vocabulary search space
        "top_p": 0.9,        # Nucleus sampling for focused answers
    }

    try:
        resp = requests.post(
            settings.ollama_url,
            json=payload,
            headers=get_ollama_headers(),
            timeout=settings.ollama_fallback_timeout,
            verify=get_ollama_verify(),
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("response", "").strip()
            token_info = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            }
            return text, token_info

        # If model not found, try to pull it once
        if resp.status_code == 404:
            logger.info(f"Model {settings.ollama_model_name} not found, attempting to pull")
            if pull_ollama_model(settings.ollama_model_name):
                # Retry the request after successful pull
                retry_resp = requests.post(
                    settings.ollama_url,
                    json=payload,
                    headers=get_ollama_headers(),
                    timeout=settings.ollama_fallback_timeout,
                    verify=get_ollama_verify(),
                )
                if retry_resp.status_code == 200:
                    data = retry_resp.json()
                    text = data.get("response", "").strip()
                    token_info = {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                    }
                    return text, token_info
                logger.error(f"Ollama retry failed ({retry_resp.status_code})")
                return _fallback_openai(prompt, "ollama retry failed")
            else:
                logger.error(f"Failed to pull model {settings.ollama_model_name}")
                return _fallback_openai(prompt, "ollama model pull failed")
        else:
            logger.error(f"Ollama request failed ({resp.status_code})")
            return _fallback_openai(prompt, f"status {resp.status_code}")

    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out")
        return _fallback_openai(prompt, "timeout")
    except requests.exceptions.ConnectionError:
        logger.warning("Cannot connect to Ollama service")
        return _fallback_openai(prompt, "connection error")
    except Exception as exc:  # pragma: no cover - best-effort network
        logger.error(f"Ollama error: {exc}")
        return _fallback_openai(prompt, "request error")

    return None, None


def _fallback_openai(prompt: str, reason: str) -> tuple[str, dict[str, int]] | tuple[None, None]:
    if not settings.openai_api_key:
        return None, None

    logger.warning(f"Falling back to OpenAI due to Ollama {reason}")
    return call_openai_chat(
        prompt,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model_name,
        timeout=settings.openai_timeout,
    )
