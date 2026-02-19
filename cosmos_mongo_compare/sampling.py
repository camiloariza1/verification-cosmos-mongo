from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import secrets
from heapq import heappop, heappush
from typing import Any
from typing import Optional
import time

from cosmos_mongo_compare.clients.base import SourceClient


def compute_sample_size(*, total: int, percentage: Optional[float], count: Optional[int]) -> int:
    if total <= 0:
        return 0
    if percentage is not None:
        size = int(total * (percentage / 100.0))
        return max(1, min(total, size))
    assert count is not None
    return max(1, min(total, int(count)))


def sample_source_documents(
    *,
    source: SourceClient,
    collection: str,
    business_key: str,
    sample_size: int,
    seed: Optional[int],
    mode: str,
    source_total: Optional[int],
    source_lookup_concurrency: int,
    deterministic_scan_log_every: int,
    deterministic_max_scan_keys: Optional[int],
    bucket_field: Optional[str],
    bucket_modulus: Optional[int],
    bucket_count: int,
    logger: logging.Logger,
) -> list[dict]:
    if sample_size <= 0:
        return []

    mode_normalized = mode.lower()
    bucket_seed = seed if seed is not None else secrets.randbits(32)

    if bucket_field is not None and bucket_modulus is not None:
        bucket_docs = _sample_documents_from_precomputed_buckets(
            source=source,
            collection=collection,
            business_key=business_key,
            sample_size=sample_size,
            bucket_field=bucket_field,
            bucket_modulus=bucket_modulus,
            bucket_count=bucket_count,
            seed=bucket_seed,
            logger=logger,
        )
        if bucket_docs:
            return bucket_docs
        logger.warning(
            "Bucket sampling produced no documents for %s; falling back to mode=%s",
            collection,
            mode_normalized,
        )
        if mode_normalized == "bucket":
            mode_normalized = "deterministic"

    if mode_normalized == "auto":
        mode_normalized = "deterministic" if seed is not None else "fast"

    if mode_normalized == "fast":
        try:
            logger.info(
                "Sampling mode=fast using source-side sampling for %s sample_size=%s",
                collection,
                sample_size,
            )
            docs = source.sample_documents(collection=collection, sample_size=sample_size)
            logger.info(
                "Fast sampling completed for %s requested=%s returned=%s",
                collection,
                sample_size,
                len(docs),
            )
            return docs
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Fast/source-side sampling failed for %s; falling back to deterministic sampling. Error: %s",
                collection,
                exc,
            )

    if seed is None:
        seed = secrets.randbits(32)
        logger.info("Using generated sampling seed=%s for %s", seed, collection)

    keys = select_deterministic_keys(
        source=source,
        collection=collection,
        business_key=business_key,
        sample_size=sample_size,
        seed=seed,
        total_keys_hint=source_total,
        max_scan_keys=deterministic_max_scan_keys,
        progress_log_every=deterministic_scan_log_every,
        logger=logger,
    )
    return _fetch_source_documents_by_keys(
        source=source,
        collection=collection,
        business_key=business_key,
        keys=keys,
        concurrency=source_lookup_concurrency,
        logger=logger,
    )


def select_deterministic_keys(
    *,
    source: SourceClient,
    collection: str,
    business_key: str,
    sample_size: int,
    seed: int,
    total_keys_hint: Optional[int],
    max_scan_keys: Optional[int],
    progress_log_every: int,
    logger: logging.Logger,
) -> list[Any]:
    """
    Deterministically select `sample_size` keys based on smallest hash(seed, key).

    This is stable across runs for a given dataset and seed, and does not depend on the
    iteration order returned by the database.
    """
    if sample_size <= 0:
        return []

    heap: list[tuple[int, Any]] = []
    scanned = 0
    started = time.monotonic()
    for key_value in source.iter_business_keys(collection=collection, business_key=business_key):
        scanned += 1
        if max_scan_keys is not None and scanned > max_scan_keys:
            logger.warning(
                "Deterministic key scan capped for %s at max_scan_keys=%s",
                collection,
                max_scan_keys,
            )
            break
        if key_value is None:
            continue
        score = _stable_score(seed=seed, key_value=key_value)
        if len(heap) < sample_size:
            heappush(heap, (-score, key_value))
        elif score < -heap[0][0]:
            heappop(heap)
            heappush(heap, (-score, key_value))

        if scanned % progress_log_every == 0:
            _log_scan_progress(
                logger=logger,
                collection=collection,
                scanned=scanned,
                selected=len(heap),
                started=started,
                total_keys_hint=total_keys_hint,
            )

    _log_scan_progress(
        logger=logger,
        collection=collection,
        scanned=scanned,
        selected=len(heap),
        started=started,
        total_keys_hint=total_keys_hint,
        final=True,
    )

    selected = [kv for _, kv in heap]
    selected.sort(key=lambda kv: _stable_score(seed=seed, key_value=kv))
    return selected


def _stable_score(*, seed: int, key_value: Any) -> int:
    h = hashlib.sha256(f"{seed}:{key_value}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def _log_scan_progress(
    *,
    logger: logging.Logger,
    collection: str,
    scanned: int,
    selected: int,
    started: float,
    total_keys_hint: Optional[int],
    final: bool = False,
) -> None:
    elapsed = max(0.001, time.monotonic() - started)
    rate = scanned / elapsed
    if total_keys_hint is not None and scanned < total_keys_hint and rate > 0:
        eta_seconds = (total_keys_hint - scanned) / rate
        eta_str = f"{eta_seconds:.1f}s"
    else:
        eta_str = "n/a"
    prefix = "Deterministic scan complete" if final else "Deterministic scan progress"
    logger.info(
        "%s collection=%s scanned=%s selected=%s rate_docs_per_sec=%.1f elapsed_seconds=%.1f eta=%s",
        prefix,
        collection,
        scanned,
        selected,
        rate,
        elapsed,
        eta_str,
    )


def _fetch_source_documents_by_keys(
    *,
    source: SourceClient,
    collection: str,
    business_key: str,
    keys: list[Any],
    concurrency: int,
    logger: logging.Logger,
) -> list[dict]:
    if not keys:
        return []

    started = time.monotonic()
    docs: list[dict] = []
    logger.info(
        "Fetching sampled source docs collection=%s keys=%s concurrency=%s",
        collection,
        len(keys),
        concurrency,
    )

    def fetch_one(key_value: Any) -> Optional[dict]:
        return source.find_by_business_key(collection=collection, business_key=business_key, key_value=key_value)

    if concurrency <= 1 or len(keys) == 1:
        for idx, key_value in enumerate(keys, start=1):
            doc = fetch_one(key_value)
            if doc is not None:
                docs.append(doc)
            if idx % 1000 == 0:
                logger.info("Source fetch progress collection=%s fetched=%s/%s", collection, idx, len(keys))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for idx, doc in enumerate(executor.map(fetch_one, keys), start=1):
                if doc is not None:
                    docs.append(doc)
                if idx % 1000 == 0:
                    logger.info("Source fetch progress collection=%s fetched=%s/%s", collection, idx, len(keys))

    elapsed = max(0.001, time.monotonic() - started)
    logger.info(
        "Source fetch complete collection=%s fetched=%s returned=%s elapsed_seconds=%.1f rate_docs_per_sec=%.1f",
        collection,
        len(keys),
        len(docs),
        elapsed,
        len(keys) / elapsed,
    )
    return docs


def _sample_documents_from_precomputed_buckets(
    *,
    source: SourceClient,
    collection: str,
    business_key: str,
    sample_size: int,
    bucket_field: str,
    bucket_modulus: int,
    bucket_count: int,
    seed: int,
    logger: logging.Logger,
) -> list[dict]:
    ranked_bucket_ids = list(range(bucket_modulus))
    ranked_bucket_ids.sort(key=lambda bucket: _stable_score(seed=seed, key_value=bucket))
    deduped_docs: dict[Any, dict] = {}
    step = max(1, bucket_count)
    logger.info(
        "Starting precomputed-bucket sampling collection=%s bucket_field=%s bucket_modulus=%s bucket_count=%s sample_size=%s",
        collection,
        bucket_field,
        bucket_modulus,
        bucket_count,
        sample_size,
    )
    for start in range(0, len(ranked_bucket_ids), step):
        if len(deduped_docs) >= sample_size:
            break
        selected_buckets = ranked_bucket_ids[start : start + step]
        remaining = sample_size - len(deduped_docs)
        docs = source.sample_documents_by_buckets(
            collection=collection,
            bucket_field=bucket_field,
            bucket_values=selected_buckets,
            sample_size=remaining,
        )
        for doc in docs:
            key_value = doc.get(business_key)
            if key_value is None:
                continue
            deduped_docs[key_value] = doc
        logger.info(
            "Bucket sampling progress collection=%s scanned_buckets=%s/%s docs=%s/%s",
            collection,
            min(start + step, len(ranked_bucket_ids)),
            len(ranked_bucket_ids),
            len(deduped_docs),
            sample_size,
        )
    sampled = list(deduped_docs.values())[:sample_size]
    logger.info(
        "Bucket sampling completed collection=%s returned=%s requested=%s",
        collection,
        len(sampled),
        sample_size,
    )
    return sampled
