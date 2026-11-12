"""Parallel backfill across all product_ids."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from product_enrich.config import Settings, get_settings
from product_enrich.db.repository import (
    ensure_metadata_bound,
    init_enrichments_table,
    list_failed_product_ids,
    list_product_ids,
)
from product_enrich.db.session import get_engine, session_scope
from product_enrich.enrich import EnrichResult, enrich

logger = logging.getLogger(__name__)


@dataclass
class BackfillSummary:
    total: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    failed_ids: list[int] = field(default_factory=list)

    def record(self, result: EnrichResult) -> None:
        if result.status == "succeeded":
            self.succeeded += 1
        elif result.status == "skipped":
            self.skipped += 1
        else:
            self.failed += 1
            self.failed_ids.append(result.product_id)


def _run_pool(product_ids: list[int], *, workers: int, settings: Settings) -> BackfillSummary:
    summary = BackfillSummary(total=len(product_ids))
    if not product_ids:
        return summary

    workers = max(1, workers)
    logger.info("backfill starting ids=%s workers=%s", len(product_ids), workers)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(enrich, product_id, settings): product_id for product_id in product_ids
        }
        for future in as_completed(futures):
            product_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.exception("worker crashed for product_id=%s: %s", product_id, exc)
                result = EnrichResult(product_id=product_id, status="failed", error=str(exc)[:2000])
            summary.record(result)
            logger.info(
                "progress product_id=%s status=%s (ok=%s skip=%s fail=%s / %s)",
                result.product_id,
                result.status,
                summary.succeeded,
                summary.skipped,
                summary.failed,
                summary.total,
            )

    return summary


def run_backfill(
    *,
    workers: int | None = None,
    force: bool = False,
    retry_failed: bool = True,
    settings: Settings | None = None,
) -> BackfillSummary:
    cfg = settings or get_settings()
    max_workers = workers if workers is not None else cfg.enrich_max_workers
    ensure_metadata_bound()
    init_enrichments_table(get_engine(cfg))

    with session_scope(cfg) as session:
        product_ids = list_product_ids(session, force=force)

    summary = _run_pool(product_ids, workers=max_workers, settings=cfg)

    if retry_failed and summary.failed_ids:
        # Prefer ids that ended failed in this run; also pick up any persisted failed rows.
        with session_scope(cfg) as session:
            persisted_failed = list_failed_product_ids(session)
        retry_ids = sorted(set(summary.failed_ids) | set(persisted_failed))
        logger.info("retrying %s failed product_ids once", len(retry_ids))
        retry_summary = _run_pool(retry_ids, workers=max_workers, settings=cfg)
        # Rebuild counts from retry outcomes for those ids; keep skipped/succeeded from first pass.
        # Simpler: report combined — first-pass non-failed + retry results for failed set.
        combined = BackfillSummary(total=summary.total)
        combined.succeeded = summary.succeeded + retry_summary.succeeded
        combined.skipped = summary.skipped + retry_summary.skipped
        combined.failed = retry_summary.failed
        combined.failed_ids = list(retry_summary.failed_ids)
        return combined

    return summary
