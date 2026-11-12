"""End-to-end enrich(product_id) unit of work."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from product_enrich.config import Settings, get_settings
from product_enrich.db.repository import (
    ensure_metadata_bound,
    init_enrichments_table,
    load_product_bundle,
    upsert_enrichment,
    upsert_status,
)
from product_enrich.db.session import get_engine, session_scope
from product_enrich.embed import embed_text
from product_enrich.images import fetch_product_image
from product_enrich.openai_util import make_openai_client
from product_enrich.schema import build_embedding_text
from product_enrich.search import build_search_document, upsert_search_document
from product_enrich.vision import describe_product

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrichResult:
    product_id: int
    status: str
    error: str | None = None


def enrich(product_id: int, settings: Settings | None = None) -> EnrichResult:
    """Process one product_id end-to-end. Idempotent upserts only."""
    cfg = settings or get_settings()
    logger.info("enrich start product_id=%s", product_id)
    ensure_metadata_bound()
    init_enrichments_table(get_engine(cfg))

    with session_scope(cfg) as session:
        bundle = load_product_bundle(session, product_id)
        if bundle is None:
            logger.error("product_id=%s not found", product_id)
            return EnrichResult(product_id=product_id, status="failed", error="product_not_found")

        if not bundle.source_url and not bundle.blob_url:
            upsert_status(session, product_id, status="skipped", error_message="no_image")
            logger.info("enrich skipped product_id=%s (no image)", product_id)
            return EnrichResult(product_id=product_id, status="skipped", error="no_image")

    try:
        image = fetch_product_image(
            source_url=bundle.source_url,
            blob_url=bundle.blob_url,
            settings=cfg,
        )
        if image is None:
            with session_scope(cfg) as session:
                upsert_status(session, product_id, status="skipped", error_message="image_download_failed")
            logger.info("enrich skipped product_id=%s (image download failed)", product_id)
            return EnrichResult(product_id=product_id, status="skipped", error="image_download_failed")

        client = make_openai_client(cfg)
        vision = describe_product(client, cfg, bundle, image)
        embedding_text = build_embedding_text(vision)
        vector = embed_text(client, cfg, embedding_text)

        doc = build_search_document(bundle=bundle, result=vision, vector=vector)
        upsert_search_document(cfg, doc)

        search_doc_id = str(product_id)
        with session_scope(cfg) as session:
            upsert_enrichment(
                session,
                result=vision,
                model=cfg.azure_openai_vision_deployment,
                image_used=image.url_used,
                embedding_text=embedding_text,
                search_doc_id=search_doc_id,
                status="succeeded",
                error_message=None,
            )

        logger.info("enrich succeeded product_id=%s", product_id)
        return EnrichResult(product_id=product_id, status="succeeded")

    except Exception as exc:
        err = str(exc)[:2000]
        logger.exception("enrich failed product_id=%s: %s", product_id, err)
        try:
            with session_scope(cfg) as session:
                upsert_status(session, product_id, status="failed", error_message=err)
        except Exception:
            logger.exception("could not persist failed status for product_id=%s", product_id)
        return EnrichResult(product_id=product_id, status="failed", error=err)
