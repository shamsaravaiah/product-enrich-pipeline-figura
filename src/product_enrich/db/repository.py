"""Postgres load / upsert helpers keyed by product_id."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from product_enrich.db.models import Base, Product, ProductEnrichment, ProductImage, Site
from product_enrich.schema import VisionEnrichment


@dataclass(frozen=True)
class ProductBundle:
    product_id: int
    site_id: int
    host: str
    name: str | None
    brand: str | None
    price: Decimal | None
    currency: str | None
    category_path: str | None
    product_url: str
    source_url: str | None
    blob_url: str | None


def init_enrichments_table(engine) -> None:
    """Create product_enrichments only; do not touch ingest tables."""
    ProductEnrichment.__table__.create(bind=engine, checkfirst=True)


def ensure_metadata_bound() -> None:
    # Keep Base.metadata aware of catalog tables for FK validation when creating enrichments.
    _ = (Site, Product, ProductImage, ProductEnrichment, Base)


def load_product_bundle(session: Session, product_id: int) -> ProductBundle | None:
    product = session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images), selectinload(Product.site))
    )
    if product is None:
        return None

    images = sorted(product.images or [], key=lambda img: img.position)
    primary: ProductImage | None = images[0] if images else None
    host = product.site.host if product.site else ""

    return ProductBundle(
        product_id=product.id,
        site_id=product.site_id,
        host=host,
        name=product.name,
        brand=product.brand,
        price=product.price,
        currency=product.currency,
        category_path=product.category_path,
        product_url=product.product_url,
        source_url=primary.source_url if primary else None,
        blob_url=primary.blob_url if primary else None,
    )


def list_product_ids(session: Session, *, force: bool = False) -> list[int]:
    """All product ids across hosts. Default: missing or not succeeded."""
    if force:
        rows = session.scalars(select(Product.id).order_by(Product.id)).all()
        return list(rows)

    succeeded = select(ProductEnrichment.product_id).where(
        ProductEnrichment.status == "succeeded"
    )
    rows = session.scalars(
        select(Product.id).where(Product.id.not_in(succeeded)).order_by(Product.id)
    ).all()
    return list(rows)


def list_failed_product_ids(session: Session) -> list[int]:
    rows = session.scalars(
        select(ProductEnrichment.product_id)
        .where(ProductEnrichment.status == "failed")
        .order_by(ProductEnrichment.product_id)
    ).all()
    return list(rows)


def upsert_status(
    session: Session,
    product_id: int,
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    stmt = insert(ProductEnrichment).values(
        product_id=product_id,
        status=status,
        error_message=error_message,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductEnrichment.product_id],
        set_={
            "status": status,
            "error_message": error_message,
            "updated_at": now,
        },
    )
    session.execute(stmt)


def upsert_enrichment(
    session: Session,
    *,
    result: VisionEnrichment,
    model: str,
    image_used: str,
    embedding_text: str,
    search_doc_id: str,
    status: str = "succeeded",
    error_message: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    values = {
        "product_id": result.product_id,
        "description": result.description,
        "gender": result.gender,
        "garment_type": result.garment_type,
        "colors": list(result.colors),
        "material": list(result.material),
        "style": list(result.style),
        "occasion": list(result.occasion),
        "season": list(result.season),
        "pattern": result.pattern,
        "fit": result.fit,
        "confidence": Decimal(str(round(result.confidence, 3))),
        "model": model,
        "image_used": image_used,
        "embedding_text": embedding_text,
        "search_doc_id": search_doc_id,
        "status": status,
        "error_message": error_message,
        "generated_at": now,
        "updated_at": now,
    }
    stmt = insert(ProductEnrichment).values(**values)
    update_cols = {k: stmt.excluded[k] for k in values if k != "product_id"}
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductEnrichment.product_id],
        set_=update_cols,
    )
    session.execute(stmt)
