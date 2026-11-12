# Azure access — product description + vector enrichment

**Resource group:** `rg-catalog-product-description-vector-enrichment`
**Region:** Sweden Central (`swedencentral`)
**Subscription:** `143c1f92-860e-4025-8d54-9c89b8b75130`

**Pipeline:** product image → vision model (description/tags) → text embedding → Azure AI Search (vector DB)

---

## 1) Azure OpenAI (vision + embeddings)

**Endpoint:** `https://oai-catalog-product-description-vision-embed.openai.azure.com/`
**Auth:** API key (`disableLocalAuth: false` — keys work)

| Role | Deployment name | Model | Version |
|---|---|---|---|
| Vision / product description | `deploy-gpt54mini-product-image-description` | `gpt-5.4-mini` | `2026-03-17` |
| Embeddings | `deploy-text-embedding-3-small-product-vectors` | `text-embedding-3-small` | `1` |

**Embedding dimensions:** `1536` (Search vector field must match)

Get API key:
```bash
az cognitiveservices account keys list \
  --name oai-catalog-product-description-vision-embed \
  --resource-group rg-catalog-product-description-vector-enrichment
```

Use **deployment names** in API calls (not raw model names).

---

## 2) Azure AI Search (vector DB)

**Service:** `search-catalog-product-description-vectors`
**Endpoint:** `https://search-catalog-product-description-vectors.search.windows.net`
**SKU:** Basic
**Auth:** admin key

Get admin key:
```bash
az search admin-key show \
  --service-name search-catalog-product-description-vectors \
  --resource-group rg-catalog-product-description-vector-enrichment
```

**Note:** Search service exists; **index not created yet** — create one (e.g. `products-vectors`) with a 1536-dim vector field + HNSW.

---

## 3) Env vars

```env
AZURE_OPENAI_ENDPOINT=https://oai-catalog-product-description-vision-embed.openai.azure.com/
AZURE_OPENAI_API_KEY=<from cognitiveservices keys list>
AZURE_OPENAI_VISION_DEPLOYMENT=deploy-gpt54mini-product-image-description
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=deploy-text-embedding-3-small-product-vectors
AZURE_OPENAI_EMBEDDING_DIMENSIONS=1536

AZURE_SEARCH_ENDPOINT=https://search-catalog-product-description-vectors.search.windows.net
AZURE_SEARCH_ADMIN_KEY=<from search admin-key show>
AZURE_SEARCH_INDEX_NAME=products-vectors
```

No SQL-style connection strings — use **endpoint + key** (+ deployment names for OpenAI).

---

## 4) Your work
1. Create AI Search index (`products-vectors` or agreed name)
2. Wire: image → vision deploy → text → embed deploy → upsert/search
3. Keep keys out of git; share via password manager only

---

## 5) Do not use
- Old vision deploy `deploy-gpt4o-product-image-description` — **deleted**
- `gpt-4o` / old gpt-4 versions — retired/legacy
