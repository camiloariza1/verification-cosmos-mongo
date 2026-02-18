from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from cosmos_mongo_compare.config import load_config
from cosmos_mongo_compare.logging_utils import build_logger
from cosmos_mongo_compare.orchestrator import run_compare


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cosmos-mongo-compare",
        description="Compare sampled documents between Azure Cosmos DB (Mongo API or SQL API) and MongoDB.",
    )
    parser.add_argument("--config", required=True, help="Path to YAML/JSON config file.")
    parser.add_argument("--collection", help="Run a single collection (must exist in config).")
    parser.add_argument(
        "--all-collections",
        action="store_true",
        help="List collections from Cosmos DB and compare those that have config entries.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = load_config(args.config)

    os.makedirs(cfg.logging.output_dir, exist_ok=True)
    main_log_dir = os.path.dirname(cfg.logging.main_log)
    if main_log_dir:
        os.makedirs(main_log_dir, exist_ok=True)
    logger = build_logger(cfg.logging.main_log)
    logger.info(
        "Starting compare run config=%s collection=%s all_collections=%s",
        args.config,
        args.collection or "<none>",
        args.all_collections,
    )
    logger.info(
        "Logging configured main_log=%s mismatch_output_dir=%s",
        cfg.logging.main_log,
        cfg.logging.output_dir,
    )

    try:
        run_compare(
            cfg=cfg,
            logger=logger,
            single_collection=args.collection,
            all_collections=args.all_collections,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        logger.exception("Fatal error: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
