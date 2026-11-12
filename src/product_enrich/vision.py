"""Azure OpenAI vision → validated enrichment JSON."""

from __future__ import annotations

import json
import logging
import re

from openai import AzureOpenAI

from product_enrich.config import Settings
from product_enrich.db.repository import ProductBundle
from product_enrich.images import DownloadedImage
from product_enrich.openai_util import with_backoff
from product_enrich.prompts import SYSTEM_PROMPT, build_user_text
from product_enrich.schema import VisionEnrichment

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if not match:
            raise
        return json.loads(match.group(0))


def describe_product(
    client: AzureOpenAI,
    settings: Settings,
    bundle: ProductBundle,
    image: DownloadedImage,
) -> VisionEnrichment:
    data_url = image.as_data_url()
    user_text = build_user_text(bundle)

    def _call() -> str:
        response = client.chat.completions.create(
            model=settings.azure_openai_vision_deployment,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return content

    raw = with_backoff(_call, label=f"vision product_id={bundle.product_id}")
    payload = _extract_json(raw)
    payload["product_id"] = bundle.product_id

    try:
        return VisionEnrichment.model_validate(payload)
    except Exception as first_err:
        logger.warning(
            "Vision JSON validation failed for product_id=%s (%s); retrying once",
            bundle.product_id,
            first_err,
        )
        raw2 = with_backoff(_call, label=f"vision-retry product_id={bundle.product_id}")
        payload2 = _extract_json(raw2)
        payload2["product_id"] = bundle.product_id
        return VisionEnrichment.model_validate(payload2)
