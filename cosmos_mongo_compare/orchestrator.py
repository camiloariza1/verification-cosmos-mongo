from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import time
from contextlib import suppress
from typing import Any, Optional

from cosmos_mongo_compare.clients.cosmos_mongo import CosmosMongoSourceClient
from cosmos_mongo_compare.clients.cosmos_sql import CosmosSqlSourceClient
from cosmos_mongo_compare.clients.mongo_target import MongoTargetClient
from cosmos_mongo_compare.compare import compare_documents
from cosmos_mongo_compare.config import AppConfig
from cosmos_mongo_compare.reporting import CollectionStats, clear_collection_mismatch_log, write_collection_mismatch_log
from cosmos_mongo_compare.sampling import compute_sample_size, sample_source_documents


def run_compare(
    *,
    cfg: AppConfig,
    logger: logging.Logger,
    single_collection: Optional[str],
    all_collections: bool,
) -> None:
    source = _build_source_client(cfg, logger)
    target = MongoTargetClient(cfg.mongodb.uri, cfg.mongodb.database, logger=logger)

    try:
        if single_collection:
            collections = [single_collection]
        elif all_collections:
            collections = source.list_collections()
        else:
            collections = list(cfg.collections.keys())

        for collection_name in collections:
            collection_started = time.monotonic()
            c_cfg = cfg.collections.get(collection_name, cfg.collection_defaults)
            if not c_cfg.enabled:
                logger.info("Skipping disabled collection: %s", collection_name)
                continue
            if not c_cfg.business_key:
                if collection_name in cfg.collections:
                    raise ValueError(f"Collection '{collection_name}' is enabled but has no business_key configured")
                raise ValueError(
                    f"Collection '{collection_name}' has no config entry and collection_defaults.business_key is not set"
                )

            clear_collection_mismatch_log(output_dir=cfg.logging.output_dir, collection=collection_name)
            count_started = time.monotonic()
            source_total = source.count_documents(collection_name)
            target_total = target.count_documents(collection_name)
            sample_size = compute_sample_size(
                total=source_total,
                percentage=cfg.sampling.percentage,
                count=cfg.sampling.count,
            )
            count_elapsed = time.monotonic() - count_started

            sample_started = time.monotonic()
            sampled = sample_source_documents(
                source=source,
                collection=collection_name,
                business_key=c_cfg.business_key,
                sample_size=sample_size,
                seed=cfg.sampling.seed,
                mode=cfg.sampling.mode,
                source_total=source_total,
                source_lookup_concurrency=cfg.sampling.source_lookup_concurrency,
                deterministic_scan_log_every=cfg.sampling.deterministic_scan_log_every,
                deterministic_max_scan_keys=cfg.sampling.deterministic_max_scan_keys,
                bucket_field=cfg.sampling.bucket_field,
                bucket_modulus=cfg.sampling.bucket_modulus,
                bucket_count=cfg.sampling.bucket_count,
                logger=logger,
            )
            sample_elapsed = time.monotonic() - sample_started

            stats = CollectionStats(
                collection=collection_name,
                source_total=source_total,
                target_total=target_total,
                sampled=len(sampled),
            )

            compare_started = time.monotonic()
            candidates: list[tuple[Any, dict]] = []
            for src_doc in sampled:
                key_value = src_doc.get(c_cfg.business_key)
                if key_value is None:
                    stats.source_missing_business_key += 1
                    continue
                candidates.append((key_value, src_doc))

            def compare_one(item: tuple[Any, dict]) -> tuple[str, Any, dict, Optional[dict], list]:
                key_value, src_doc = item
                tgt_doc = target.find_by_business_key(collection_name, c_cfg.business_key, key_value)
                if tgt_doc is None:
                    return ("missing", key_value, src_doc, None, [])
                diffs = compare_documents(
                    src_doc,
                    tgt_doc,
                    exclude_fields=c_cfg.exclude_fields,
                    array_order_insensitive_paths=c_cfg.array_order_insensitive_paths,
                )
                if diffs:
                    return ("mismatch", key_value, src_doc, tgt_doc, diffs)
                return ("match", key_value, src_doc, tgt_doc, [])

            if cfg.sampling.compare_concurrency <= 1 or len(candidates) <= 1:
                result_iter = map(compare_one, candidates)
            else:
                result_iter = _parallel_map(compare_one, candidates, cfg.sampling.compare_concurrency)

            processed = 0
            for result_kind, key_value, src_doc, tgt_doc, diffs in result_iter:
                processed += 1
                if processed % cfg.sampling.compare_log_every == 0:
                    elapsed = max(0.001, time.monotonic() - compare_started)
                    rate = processed / elapsed
                    logger.info(
                        "Compare progress collection=%s processed=%s/%s rate_docs_per_sec=%.1f elapsed_seconds=%.1f",
                        collection_name,
                        processed,
                        len(candidates),
                        rate,
                        elapsed,
                    )

                if result_kind == "missing":
                    stats.missing_in_target += 1
                    continue

                stats.found_in_both += 1
                if result_kind == "mismatch":
                    stats.mismatched += 1
                    assert tgt_doc is not None
                    write_collection_mismatch_log(
                        output_dir=cfg.logging.output_dir,
                        collection=collection_name,
                        business_key=c_cfg.business_key,
                        business_key_value=key_value,
                        source_doc=src_doc,
                        target_doc=tgt_doc,
                        diffs=diffs,
                    )
                else:
                    stats.matched += 1

            compare_elapsed = time.monotonic() - compare_started
            total_elapsed = time.monotonic() - collection_started
            logger.info(stats.to_log_line())
            logger.info(
                "Collection phase timings collection=%s count_seconds=%.2f sample_seconds=%.2f compare_seconds=%.2f total_seconds=%.2f",
                collection_name,
                count_elapsed,
                sample_elapsed,
                compare_elapsed,
                total_elapsed,
            )
    finally:
        with suppress(Exception):
            source.close()
        with suppress(Exception):
            target.close()


def _build_source_client(cfg: AppConfig, logger: logging.Logger):
    if cfg.cosmos.api == "mongo":
        assert cfg.cosmos.uri is not None
        return CosmosMongoSourceClient(cfg.cosmos.uri, cfg.cosmos.database, logger=logger)
    if cfg.cosmos.api == "sql":
        assert cfg.cosmos.endpoint is not None and cfg.cosmos.key is not None
        return CosmosSqlSourceClient(
            cfg.cosmos.endpoint,
            cfg.cosmos.key,
            cfg.cosmos.database,
            logger=logger,
            retry_max_attempts=cfg.sampling.cosmos_retry_max_attempts,
            retry_base_delay_ms=cfg.sampling.cosmos_retry_base_delay_ms,
        )
    raise AssertionError(f"Unknown Cosmos API: {cfg.cosmos.api}")


def _parallel_map(func, items, max_workers: int):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(func, items):
            yield result
