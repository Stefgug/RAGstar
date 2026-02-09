"""OpenAI client helpers for fallback usage."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def call_openai_chat(
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    timeout: int,
) -> tuple[str, dict[str, int]] | tuple[None, None]:
    if not api_key:
        logger.warning("OpenAI API key is not configured; fallback is disabled")
        return None, None

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 256,
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_build_headers(api_key),
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        logger.warning("OpenAI chat request timed out")
        return None, None
    except requests.exceptions.ConnectionError as exc:
        logger.warning(f"OpenAI connection error: {exc}")
        return None, None
    except Exception as exc:  # pragma: no cover - network error
        logger.error(f"OpenAI chat request failed: {exc}")
        return None, None

    if resp.status_code != 200:
        logger.error(f"OpenAI chat request failed ({resp.status_code}): {resp.text}")
        return None, None

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        logger.error("OpenAI chat response missing choices")
        return None, None

    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    usage = data.get("usage") or {}
    token_info = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    return text, token_info


def call_openai_embeddings(
    texts: list[str],
    api_key: str,
    base_url: str,
    model: str,
    timeout: int,
    dimensions: int | None = None,
) -> list[list[float]] | None:
    if not api_key:
        logger.warning("OpenAI API key is not configured; fallback is disabled")
        return None

    url = f"{base_url.rstrip('/')}/embeddings"
    payload: dict[str, Any] = {
        "model": model,
        "input": texts,
    }
    if dimensions is not None:
        payload["dimensions"] = dimensions

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_build_headers(api_key),
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        logger.warning("OpenAI embeddings request timed out")
        return None
    except requests.exceptions.ConnectionError as exc:
        logger.warning(f"OpenAI connection error: {exc}")
        return None
    except Exception as exc:  # pragma: no cover - network error
        logger.error(f"OpenAI embeddings request failed: {exc}")
        return None

    if resp.status_code != 200:
        logger.error(f"OpenAI embeddings request failed ({resp.status_code}): {resp.text}")
        return None

    data = resp.json()
    items = data.get("data") or []
    if not items:
        logger.error("OpenAI embeddings response missing data")
        return None

    embeddings = [item.get("embedding") for item in items]
    if any(embedding is None for embedding in embeddings):
        logger.error("OpenAI embeddings response missing embedding vectors")
        return None

    return embeddings
