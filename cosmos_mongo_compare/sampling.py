from __future__ import annotations

import hashlib
import logging
import secrets
from heapq import heappop, heappush
from typing import Any
from typing import Optional

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
    logger: logging.Logger,
) -> list[dict]:
    if sample_size <= 0:
        return []

    if seed is None:
        try:
            return source.sample_documents(collection=collection, sample_size=sample_size)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Server-side sampling failed for %s; falling back to seeded sampling. Error: %s", collection, exc)
            seed = secrets.randbits(32)
            logger.info("Using generated sampling seed=%s for %s", seed, collection)

    keys = select_deterministic_keys(
        source=source,
        collection=collection,
        business_key=business_key,
        sample_size=sample_size,
        seed=seed,
    )
    docs: list[dict] = []
    for key_value in keys:
        doc = source.find_by_business_key(collection=collection, business_key=business_key, key_value=key_value)
        if doc is not None:
            docs.append(doc)
    return docs


def select_deterministic_keys(
    *,
    source: SourceClient,
    collection: str,
    business_key: str,
    sample_size: int,
    seed: int,
) -> list[Any]:
    """
    Deterministically select `sample_size` keys based on smallest hash(seed, key).

    This is stable across runs for a given dataset and seed, and does not depend on the
    iteration order returned by the database.
    """
    if sample_size <= 0:
        return []

    heap: list[tuple[int, Any]] = []
    for key_value in source.iter_business_keys(collection=collection, business_key=business_key):
        if key_value is None:
            continue
        score = _stable_score(seed=seed, key_value=key_value)
        if len(heap) < sample_size:
            heappush(heap, (-score, key_value))
            continue
        if score < -heap[0][0]:
            heappop(heap)
            heappush(heap, (-score, key_value))

    selected = [kv for _, kv in heap]
    selected.sort(key=lambda kv: _stable_score(seed=seed, key_value=kv))
    return selected


def _stable_score(*, seed: int, key_value: Any) -> int:
    h = hashlib.sha256(f"{seed}:{key_value}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)
