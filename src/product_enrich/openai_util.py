"""Shared Azure OpenAI client + 429 backoff."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from openai import APIStatusError, AzureOpenAI, RateLimitError

from product_enrich.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def make_openai_client(settings: Settings) -> AzureOpenAI:
    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required")
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 6,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    label: str = "openai",
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RateLimitError as exc:
            last_exc = exc
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.5 + random.random())
            logger.warning("%s rate-limited (attempt %s/%s); sleep %.1fs", label, attempt, max_attempts, delay)
            time.sleep(delay)
        except APIStatusError as exc:
            if exc.status_code != 429:
                raise
            last_exc = exc
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.5 + random.random())
            logger.warning("%s HTTP 429 (attempt %s/%s); sleep %.1fs", label, attempt, max_attempts, delay)
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
