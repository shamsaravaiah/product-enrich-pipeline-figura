"""Vision prompts for fashion catalog tagging."""

from __future__ import annotations

from product_enrich.db.repository import ProductBundle

SYSTEM_PROMPT = """You are tagging fashion catalog products for search and retrieval.
Use the product image as primary evidence. Use name, brand, and category_path only as hints.
Return ONLY valid JSON matching this exact schema (no markdown, no commentary):
{
  "product_id": <int>,
  "description": "<1-2 factual English sentences, max ~300 chars>",
  "gender": "men|women|unisex|kids|unknown",
  "garment_type": "shirt|t-shirt|hoodie|sweater|blazer|jacket|coat|dress|skirt|trousers|jeans|shorts|shoes|boots|sneakers|bag|accessory|hat|other|unknown",
  "colors": ["black|white|grey|beige|brown|navy|blue|green|red|pink|purple|yellow|orange|multicolor|metallic|unknown"],
  "material": ["cotton|wool|denim|leather|synthetic|linen|silk|unknown"],
  "style": ["casual|smart-casual|formal|sport|streetwear|minimal|luxury|unknown"],
  "occasion": ["date|work|evening|party|casual|outdoor|travel|sport|unknown"],
  "season": ["spring|summer|autumn|winter|all-season|unknown"],
  "pattern": "solid|striped|checked|printed|logo|other|unknown",
  "fit": "slim|regular|relaxed|oversized|unknown",
  "confidence": <float 0-1>
}
Rules:
- Prefer "unknown" over guessing.
- colors: 1-3 values, primary color first.
- style/occasion: 1-4 values; season: 1-2 values.
- Description must be factual and useful for semantic search, not marketing fluff.
- product_id must match the given product_id exactly.
"""


def build_user_text(bundle: ProductBundle) -> str:
    price = str(bundle.price) if bundle.price is not None else "null"
    return (
        "Tag this catalog product from the image and context.\n"
        f"product_id: {bundle.product_id}\n"
        f"name: {bundle.name or ''}\n"
        f"brand: {bundle.brand or ''}\n"
        f"category_path: {bundle.category_path or ''}\n"
        f"price: {price}\n"
        f"currency: {bundle.currency or ''}\n"
        f"product_url: {bundle.product_url}\n"
        "Return JSON only."
    )
