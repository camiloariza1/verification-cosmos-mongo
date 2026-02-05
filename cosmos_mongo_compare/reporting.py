from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from cosmos_mongo_compare.compare import Diff
from cosmos_mongo_compare.serialization import json_default


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _collection_log_path(*, output_dir: str, collection: str) -> str:
    safe = _FILENAME_SAFE_RE.sub("_", collection).strip("._-") or "collection"
    return os.path.join(output_dir, f"{safe}_mismatches.jsonl")


@dataclass
class CollectionStats:
    collection: str
    source_total: int
    target_total: int
    sampled: int
    found_in_both: int = 0
    missing_in_target: int = 0
    source_missing_business_key: int = 0
    matched: int = 0
    mismatched: int = 0

    def to_log_line(self) -> str:
        missing_in_either = self.missing_in_target + self.source_missing_business_key
        return (
            f"{self.collection} | "
            f"source_total={self.source_total} target_total={self.target_total} "
            f"sampled={self.sampled} found_in_both={self.found_in_both} "
            f"missing_in_either={missing_in_either} missing_in_target={self.missing_in_target} "
            f"source_missing_business_key={self.source_missing_business_key} "
            f"matched={self.matched} mismatched={self.mismatched}"
        )


def clear_collection_mismatch_log(*, output_dir: str, collection: str) -> None:
    path = _collection_log_path(output_dir=output_dir, collection=collection)
    try:
        os.remove(path)
    except FileNotFoundError:
        return


def write_collection_mismatch_log(
    *,
    output_dir: str,
    collection: str,
    business_key: str,
    business_key_value: Any,
    source_doc: dict,
    target_doc: dict,
    diffs: Iterable[Diff],
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    path = _collection_log_path(output_dir=output_dir, collection=collection)
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "business_key": business_key,
        "business_key_value": business_key_value,
        "differences": [d.__dict__ for d in diffs],
        "source": source_doc,
        "target": target_doc,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=json_default) + "\n")
