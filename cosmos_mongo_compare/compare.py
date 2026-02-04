from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from typing import Optional


@dataclass(frozen=True)
class Diff:
    path: str
    kind: str  # missing_in_source | missing_in_target | type_mismatch | value_mismatch
    source: Optional[Any]
    target: Optional[Any]


def compare_documents(
    source_doc: dict,
    target_doc: dict,
    *,
    exclude_fields: Iterable[str] = (),
    array_order_insensitive_paths: Iterable[str] = (),
) -> list[Diff]:
    exclude_anywhere, exclude_paths = _build_exclude_sets(exclude_fields)
    pruned_source = _prune(source_doc, exclude_anywhere=exclude_anywhere, exclude_paths=exclude_paths, path="")
    pruned_target = _prune(target_doc, exclude_anywhere=exclude_anywhere, exclude_paths=exclude_paths, path="")
    insensitive = set(array_order_insensitive_paths)
    return _diff(pruned_source, pruned_target, path="", array_order_insensitive_paths=insensitive)


def _build_exclude_sets(exclude_fields: Iterable[str]) -> tuple[set[str], set[str]]:
    exclude_anywhere: set[str] = set()
    exclude_paths: set[str] = set()
    for f in exclude_fields:
        if "." in f:
            exclude_paths.add(f)
        else:
            exclude_anywhere.add(f)
    return exclude_anywhere, exclude_paths


def _prune(value: Any, *, exclude_anywhere: set[str], exclude_paths: set[str], path: str) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            next_path = f"{path}.{k}" if path else k
            if k in exclude_anywhere or next_path in exclude_paths:
                continue
            out[k] = _prune(v, exclude_anywhere=exclude_anywhere, exclude_paths=exclude_paths, path=next_path)
        return out
    if isinstance(value, list):
        return [_prune(v, exclude_anywhere=exclude_anywhere, exclude_paths=exclude_paths, path=path) for v in value]
    return value


def _diff(a: Any, b: Any, *, path: str, array_order_insensitive_paths: set[str]) -> list[Diff]:
    if a is None and b is None:
        return []

    if type(a) is not type(b):
        return [Diff(path=path or "$", kind="type_mismatch", source=_type_name(a), target=_type_name(b))]

    if isinstance(a, dict):
        diffs: list[Diff] = []
        keys = set(a.keys()) | set(b.keys())
        for key in sorted(keys):
            next_path = f"{path}.{key}" if path else key
            if key not in a:
                diffs.append(Diff(path=next_path, kind="missing_in_source", source=None, target=b.get(key)))
            elif key not in b:
                diffs.append(Diff(path=next_path, kind="missing_in_target", source=a.get(key), target=None))
            else:
                diffs.extend(_diff(a[key], b[key], path=next_path, array_order_insensitive_paths=array_order_insensitive_paths))
        return diffs

    if isinstance(a, list):
        if path in array_order_insensitive_paths:
            return _diff_list_insensitive(a, b, path)
        return _diff_list_sensitive(a, b, path, array_order_insensitive_paths=array_order_insensitive_paths)

    if not _values_equal(a, b):
        return [Diff(path=path or "$", kind="value_mismatch", source=a, target=b)]
    return []


def _diff_list_sensitive(a: list, b: list, path: str, *, array_order_insensitive_paths: set[str]) -> list[Diff]:
    diffs: list[Diff] = []
    if len(a) != len(b):
        diffs.append(Diff(path=path or "$", kind="value_mismatch", source=f"len={len(a)}", target=f"len={len(b)}"))
    for i in range(min(len(a), len(b))):
        diffs.extend(_diff(a[i], b[i], path=f"{path}[{i}]", array_order_insensitive_paths=array_order_insensitive_paths))
    if len(a) > len(b):
        for i in range(len(b), len(a)):
            diffs.append(Diff(path=f"{path}[{i}]", kind="missing_in_target", source=a[i], target=None))
    elif len(b) > len(a):
        for i in range(len(a), len(b)):
            diffs.append(Diff(path=f"{path}[{i}]", kind="missing_in_source", source=None, target=b[i]))
    return diffs


def _diff_list_insensitive(a: list, b: list, path: str) -> list[Diff]:
    ca = Counter(_canonicalize(v) for v in a)
    cb = Counter(_canonicalize(v) for v in b)
    if ca == cb:
        return []
    return [Diff(path=path or "$", kind="value_mismatch", source=dict(ca), target=dict(cb))]


def _canonicalize(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=_json_default, ensure_ascii=False)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _values_equal(a: Any, b: Any) -> bool:
    return a == b


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    return type(value).__name__
