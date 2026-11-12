# product-enrich

Standalone pipeline that enriches catalog products on the ingest VM:

**Postgres product + image → Azure OpenAI vision (gpt-5.4-mini) → Postgres description/tags → embedding → Azure AI Search**

Join key across every store: **`product_id` = `products.id`**.

| Store | What it holds | Link |
| --- | --- | --- |
| Postgres `products` / `product_images` | Catalog facts + image URLs | `products.id` / `product_images.product_id` |
| Postgres `product_enrichments` | AI description + structured tags (source of truth for text) | PK/FK `product_id` |
| Azure Blob | Optional private image bytes | via `product_images.blob_url` for that `product_id` |
| Azure AI Search (`products-vectors`) | Filter fields + `content_vector` for semantic search | Document key = `str(product_id)` |

Re-runs are idempotent: upserts by `product_id` only (no duplicate rows or Search docs).

---

## Setup

```bash
cd product-vectorise
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# fill DATABASE_URL, OpenAI, Search, optional Blob
```

Or without install:

```bash
pip install -r requirements.txt
export PYTHONPATH=src
```

### Env vars

See [`.env.example`](.env.example). Important defaults:

- Vision deploy: `deploy-gpt54mini-product-image-description`
- Embedding deploy: `deploy-text-embedding-3-small-product-vectors` (1536 dims)
- Search index: `products-vectors`
- Workers: `ENRICH_MAX_WORKERS=4`

Azure endpoint notes: [`vector.md`](vector.md).

---

## One-time init

```bash
python -m product_enrich init-db       # create product_enrichments
python -m product_enrich init-search   # create AI Search index (HNSW / cosine / 1536)
```

`init-db` only creates `product_enrichments`; it does not alter ingest tables.

---

## Run

Single product:

```bash
python -m product_enrich enrich --product-id 1
```

Backfill all hosts (products missing `status=succeeded`):

```bash
python -m product_enrich enrich --backfill --workers 5
```

Force re-enrich everything:

```bash
python -m product_enrich enrich --backfill --force --workers 4
```

Each worker processes **one `product_id` end-to-end** (load → image → vision JSON → Postgres → embed → Search). OpenAI 429s use exponential backoff.

---

## Vision JSON contract

The model must return strict JSON (validated with Pydantic enums), e.g.:

```json
{
  "product_id": 1,
  "description": "Black slim-fit cotton shirt suited for a casual date",
  "gender": "men",
  "garment_type": "shirt",
  "colors": ["black"],
  "material": ["cotton"],
  "style": ["casual", "smart-casual"],
  "occasion": ["date", "evening", "casual"],
  "season": ["all-season"],
  "pattern": "solid",
  "fit": "slim",
  "confidence": 0.86
}
```

Embedding text = description + tag line (**no price**). Price stays a filterable Search/Postgres field.

---

## Status values

`product_enrichments.status`: `succeeded` | `failed` | `skipped` (no usable image).

Backfill retries failed ids once by default (`--no-retry` to disable).

---

## Later: ingest-hm

This package is standalone and reads the same Postgres/Blob as ingest-hm. It can be wired into that repo later without changing the join key or upsert semantics.

## Out of scope (v1)

Service Bus, Container Apps, host-scoped Products API reads.
