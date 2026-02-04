from __future__ import annotations

import logging
from typing import Optional

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
    target = MongoTargetClient(cfg.mongodb.uri, cfg.mongodb.database)

    if single_collection:
        collections = [single_collection]
    elif all_collections:
        collections = source.list_collections()
    else:
        collections = list(cfg.collections.keys())

    for collection_name in collections:
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
        source_total = source.count_documents(collection_name)
        target_total = target.count_documents(collection_name)
        sample_size = compute_sample_size(
            total=source_total,
            percentage=cfg.sampling.percentage,
            count=cfg.sampling.count,
        )

        sampled = sample_source_documents(
            source=source,
            collection=collection_name,
            business_key=c_cfg.business_key,
            sample_size=sample_size,
            seed=cfg.sampling.seed,
            logger=logger,
        )

        stats = CollectionStats(
            collection=collection_name,
            source_total=source_total,
            target_total=target_total,
            sampled=len(sampled),
        )

        for src_doc in sampled:
            key_value = src_doc.get(c_cfg.business_key)
            if key_value is None:
                stats.source_missing_business_key += 1
                continue

            tgt_doc = target.find_by_business_key(collection_name, c_cfg.business_key, key_value)
            if tgt_doc is None:
                stats.missing_in_target += 1
                continue

            stats.found_in_both += 1
            diffs = compare_documents(
                src_doc,
                tgt_doc,
                exclude_fields=c_cfg.exclude_fields,
                array_order_insensitive_paths=c_cfg.array_order_insensitive_paths,
            )
            if diffs:
                stats.mismatched += 1
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

        logger.info(stats.to_log_line())


def _build_source_client(cfg: AppConfig, logger: logging.Logger):
    if cfg.cosmos.api == "mongo":
        assert cfg.cosmos.uri is not None
        return CosmosMongoSourceClient(cfg.cosmos.uri, cfg.cosmos.database)
    if cfg.cosmos.api == "sql":
        assert cfg.cosmos.endpoint is not None and cfg.cosmos.key is not None
        return CosmosSqlSourceClient(cfg.cosmos.endpoint, cfg.cosmos.key, cfg.cosmos.database, logger=logger)
    raise AssertionError(f"Unknown Cosmos API: {cfg.cosmos.api}")
