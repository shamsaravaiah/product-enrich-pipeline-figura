from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ingest:ingest@localhost:5432/ingest"

    azure_storage_connection_string: str = ""
    azure_blob_container: str = "catalog-images"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_vision_deployment: str = "deploy-gpt54mini-product-image-description"
    azure_openai_embedding_deployment: str = "deploy-text-embedding-3-small-product-vectors"
    azure_openai_embedding_dimensions: int = 1536

    azure_search_endpoint: str = ""
    azure_search_admin_key: str = ""
    azure_search_index_name: str = "products-vectors"

    enrich_max_workers: int = 4
    request_timeout_seconds: float = 45.0
    max_image_bytes: int = 8_000_000
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ProductEnrich/1.0"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
