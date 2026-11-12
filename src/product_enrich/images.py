"""Download primary product image: source_url first, else Blob."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from azure.storage.blob import BlobServiceClient

from product_enrich.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    content_type: str
    url_used: str

    def as_data_url(self) -> str:
        b64 = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.content_type};base64,{b64}"


def _guess_content_type(header: str | None, fallback: str = "image/jpeg") -> str:
    if not header:
        return fallback
    ctype = header.split(";")[0].strip().lower()
    if ctype.startswith("image/") and ctype != "image/svg+xml":
        return ctype
    return fallback


def download_from_url(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    user_agent: str,
    timeout: float,
) -> DownloadedImage | None:
    try:
        with client.stream(
            "GET",
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        ) as response:
            if response.status_code != 200:
                logger.info("Image HTTP %s for %s", response.status_code, url)
                return None
            content_type = _guess_content_type(response.headers.get("content-type"))
            if not content_type.startswith("image/") or content_type == "image/svg+xml":
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    logger.warning("Image too large for %s", url)
                    return None
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data:
                return None
            return DownloadedImage(data=data, content_type=content_type, url_used=url)
    except Exception as exc:
        logger.info("Failed to download %s: %s", url, exc)
        return None


def _blob_name_from_url(blob_url: str, container: str) -> str | None:
    parsed = urlparse(blob_url)
    path = parsed.path.lstrip("/")
    prefix = f"{container}/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    # path may already be blob name if URL shape differs
    if "/" in path:
        # account.blob.core.windows.net/container/blob/path
        parts = path.split("/", 1)
        if len(parts) == 2 and parts[0] == container:
            return parts[1]
        return path
    return path or None


def download_from_blob(
    *,
    blob_url: str,
    settings: Settings,
) -> DownloadedImage | None:
    conn = (settings.azure_storage_connection_string or "").strip()
    container = (settings.azure_blob_container or "").strip()
    if not conn or not container:
        logger.warning("Blob fallback skipped: missing connection string or container")
        return None
    blob_name = _blob_name_from_url(blob_url, container)
    if not blob_name:
        logger.warning("Could not parse blob name from %s", blob_url)
        return None
    try:
        service = BlobServiceClient.from_connection_string(conn)
        blob_client = service.get_blob_client(container=container, blob=blob_name)
        downloader = blob_client.download_blob()
        data = downloader.readall()
        if not data or len(data) > settings.max_image_bytes:
            return None
        props = blob_client.get_blob_properties()
        content_type = _guess_content_type(
            getattr(getattr(props, "content_settings", None), "content_type", None)
        )
        return DownloadedImage(data=data, content_type=content_type, url_used=blob_url)
    except Exception as exc:
        logger.info("Blob download failed for %s: %s", blob_url, exc)
        return None


def fetch_product_image(
    *,
    source_url: str | None,
    blob_url: str | None,
    settings: Settings,
    http_client: httpx.Client | None = None,
) -> DownloadedImage | None:
    owns_client = http_client is None
    client = http_client or httpx.Client()
    try:
        if source_url:
            img = download_from_url(
                client,
                source_url,
                max_bytes=settings.max_image_bytes,
                user_agent=settings.user_agent,
                timeout=settings.request_timeout_seconds,
            )
            if img is not None:
                return img
        if blob_url:
            return download_from_blob(blob_url=blob_url, settings=settings)
        return None
    finally:
        if owns_client:
            client.close()
