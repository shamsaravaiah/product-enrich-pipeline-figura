"""CLI: init-db, init-search, enrich --product-id / --backfill."""

from __future__ import annotations

import argparse
import logging
import sys

from product_enrich.backfill import run_backfill
from product_enrich.config import get_settings
from product_enrich.db.repository import ensure_metadata_bound, init_enrichments_table
from product_enrich.db.session import get_engine
from product_enrich.enrich import enrich
from product_enrich.search import create_search_index


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="product-enrich",
        description="Product description + vector enrichment (join key: product_id)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create product_enrichments table if missing")
    sub.add_parser("init-search", help="Create Azure AI Search index if missing")

    enrich_p = sub.add_parser("enrich", help="Enrich one product or backfill all")
    group = enrich_p.add_mutually_exclusive_group(required=True)
    group.add_argument("--product-id", type=int, help="Single products.id to enrich")
    group.add_argument("--backfill", action="store_true", help="Process all missing product_ids")
    enrich_p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Thread pool size for backfill (default ENRICH_MAX_WORKERS / 4)",
    )
    enrich_p.add_argument(
        "--force",
        action="store_true",
        help="Re-enrich all products, including already succeeded",
    )
    enrich_p.add_argument(
        "--no-retry",
        action="store_true",
        help="Skip second pass over failed ids",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    settings = get_settings()

    if args.command == "init-db":
        ensure_metadata_bound()
        init_enrichments_table(get_engine(settings))
        print("product_enrichments table ready")
        return 0

    if args.command == "init-search":
        name = create_search_index(settings)
        print(f"search index ready: {name}")
        return 0

    if args.command == "enrich":
        if args.product_id is not None:
            result = enrich(args.product_id, settings)
            print(f"product_id={result.product_id} status={result.status}" + (
                f" error={result.error}" if result.error else ""
            ))
            return 0 if result.status in {"succeeded", "skipped"} else 1

        summary = run_backfill(
            workers=args.workers,
            force=args.force,
            retry_failed=not args.no_retry,
            settings=settings,
        )
        print(
            f"backfill done total={summary.total} "
            f"succeeded={summary.succeeded} skipped={summary.skipped} "
            f"failed={summary.failed}"
        )
        if summary.failed_ids:
            print(f"failed_ids={summary.failed_ids[:50]}" + (
                "..." if len(summary.failed_ids) > 50 else ""
            ))
        return 0 if summary.failed == 0 else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
