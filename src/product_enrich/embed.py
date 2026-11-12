"""Azure OpenAI embeddings."""

from __future__ import annotations

from openai import AzureOpenAI

from product_enrich.config import Settings
from product_enrich.openai_util import with_backoff


def embed_text(client: AzureOpenAI, settings: Settings, text: str) -> list[float]:
    def _call() -> list[float]:
        kwargs: dict = {
            "model": settings.azure_openai_embedding_deployment,
            "input": text,
        }
        if settings.azure_openai_embedding_dimensions:
            kwargs["dimensions"] = settings.azure_openai_embedding_dimensions
        response = client.embeddings.create(**kwargs)
        return list(response.data[0].embedding)

    return with_backoff(_call, label="embedding")
