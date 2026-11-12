"""Minimal catalog models + product_enrichments."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("host", "locale_prefix", name="uq_sites_host_prefix"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    locale_prefix: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    products: Mapped[list["Product"]] = relationship(back_populates="site")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("site_id", "product_url", name="uq_products_site_url"),
        Index("ix_products_site_sku", "site_id", "sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    availability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    category_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    site: Mapped[Site] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        order_by="ProductImage.position",
    )
    enrichment: Mapped["ProductEnrichment | None"] = relationship(
        back_populates="product",
        uselist=False,
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    blob_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductEnrichment(Base):
    __tablename__ = "product_enrichments"
    __table_args__ = (
        Index("ix_product_enrichments_status", "status"),
        Index("ix_product_enrichments_gender", "gender"),
        Index("ix_product_enrichments_garment_type", "garment_type"),
        Index("ix_product_enrichments_colors", "colors", postgresql_using="gin"),
        Index("ix_product_enrichments_occasion", "occasion", postgresql_using="gin"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    garment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    colors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    material: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    style: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    occasion: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    season: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="enrichment")
