"""Azure AI Search index create + document upsert by product_id."""

from __future__ import annotations

import logging
from decimal import Decimal

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from product_enrich.config import Settings
from product_enrich.db.repository import ProductBundle
from product_enrich.schema import VisionEnrichment

logger = logging.getLogger(__name__)


def _index_client(settings: Settings) -> SearchIndexClient:
    if not settings.azure_search_endpoint or not settings.azure_search_admin_key:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY are required")
    return SearchIndexClient(
        endpoint=settings.azure_search_endpoint.rstrip("/"),
        credential=AzureKeyCredential(settings.azure_search_admin_key),
    )


def _search_client(settings: Settings) -> SearchClient:
    if not settings.azure_search_endpoint or not settings.azure_search_admin_key:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY are required")
    return SearchClient(
        endpoint=settings.azure_search_endpoint.rstrip("/"),
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_admin_key),
    )


def create_search_index(settings: Settings) -> str:
    """Create products-vectors index if missing. Returns index name."""
    dims = settings.azure_openai_embedding_dimensions
    name = settings.azure_search_index_name
    client = _index_client(settings)

    existing = {idx.name for idx in client.list_indexes()}
    if name in existing:
        logger.info("Search index %s already exists", name)
        return name

    fields = [
        SimpleField(name="product_id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="site_id", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="host", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="name", type=SearchFieldDataType.String),
        SearchableField(name="brand", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="price", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="currency", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="category_path", type=SearchFieldDataType.String),
        SimpleField(name="gender", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="garment_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(
            name="colors",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(
            name="style",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(
            name="occasion",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(
            name="season",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
        SimpleField(name="blob_url", type=SearchFieldDataType.String),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dims,
            vector_search_profile_name="content-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[
            VectorSearchProfile(
                name="content-vector-profile",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    index = SearchIndex(name=name, fields=fields, vector_search=vector_search)
    client.create_index(index)
    logger.info("Created Search index %s (dims=%s)", name, dims)
    return name


def build_search_document(
    *,
    bundle: ProductBundle,
    result: VisionEnrichment,
    vector: list[float],
) -> dict:
    price: float | None
    if bundle.price is None:
        price = None
    elif isinstance(bundle.price, Decimal):
        price = float(bundle.price)
    else:
        price = float(bundle.price)

    return {
        "product_id": str(bundle.product_id),
        "site_id": bundle.site_id,
        "host": bundle.host or "",
        "name": bundle.name or "",
        "brand": bundle.brand or "",
        "price": price,
        "currency": bundle.currency or "",
        "category_path": bundle.category_path or "",
        "gender": result.gender,
        "garment_type": result.garment_type,
        "colors": list(result.colors),
        "style": list(result.style),
        "occasion": list(result.occasion),
        "season": list(result.season),
        "source_url": bundle.source_url or "",
        "blob_url": bundle.blob_url or "",
        "description": result.description,
        "content_vector": vector,
    }


def upsert_search_document(settings: Settings, document: dict) -> None:
    client = _search_client(settings)
    result = client.merge_or_upload_documents(documents=[document])
    for r in result:
        if not r.succeeded:
            raise RuntimeError(f"Search upsert failed for {document.get('product_id')}: {r.error_message}")
