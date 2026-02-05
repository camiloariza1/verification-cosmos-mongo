from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml


@dataclass(frozen=True)
class CosmosConfig:
    api: str  # "mongo" | "sql"
    database: str
    uri: Optional[str] = None  # mongo api
    endpoint: Optional[str] = None  # sql api
    key: Optional[str] = None  # sql api


@dataclass(frozen=True)
class MongoConfig:
    uri: str
    database: str


@dataclass(frozen=True)
class SamplingConfig:
    percentage: Optional[float] = None
    count: Optional[int] = None
    seed: Optional[int] = None


@dataclass(frozen=True)
class LoggingConfig:
    main_log: str
    output_dir: str


@dataclass(frozen=True)
class CollectionConfig:
    business_key: Optional[str] = None
    enabled: bool = True
    exclude_fields: tuple[str, ...] = ()
    array_order_insensitive_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppConfig:
    cosmos: CosmosConfig
    mongodb: MongoConfig
    sampling: SamplingConfig
    logging: LoggingConfig
    collections: Mapping[str, CollectionConfig]
    collection_defaults: CollectionConfig


class ConfigError(ValueError):
    pass


_FIELD_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _env_nonempty(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _expand_env(value: str, where: str) -> str:
    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        env_val = _env_nonempty(var)
        if env_val is None:
            raise ConfigError(f"Missing environment variable {var} referenced at {where}")
        return env_val

    return _ENV_VAR_RE.sub(repl, value)


def _expand_env_in_obj(obj: Any, where: str) -> Any:
    if isinstance(obj, str):
        return _expand_env(obj, where) if "${" in obj else obj
    if isinstance(obj, list):
        return [_expand_env_in_obj(v, f"{where}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, dict):
        return {k: _expand_env_in_obj(v, f"{where}.{k}") for k, v in obj.items()}
    return obj


def _require(mapping: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"Missing required config key: {where}.{key}")
    return mapping[key]


def _as_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"Expected non-empty string at {where}")
    return value


def _as_int(value: Any, where: str) -> int:
    if not isinstance(value, int):
        raise ConfigError(f"Expected integer at {where}")
    return value


def _as_float(value: Any, where: str) -> float:
    if not isinstance(value, (int, float)):
        raise ConfigError(f"Expected number at {where}")
    return float(value)


def _as_str_list(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"Expected list[str] at {where}")
    return tuple(value)


def _as_mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"Expected object/map at {where}")
    return value


def _as_field_path(value: Any, where: str) -> str:
    s = _as_str(value, where)
    parts = s.split(".")
    if not parts or any(not p or _FIELD_PATH_SEGMENT_RE.fullmatch(p) is None for p in parts):
        raise ConfigError(
            f"Expected field path at {where} (e.g. 'id', '_id', 'customer.id', 'customer-id'; dot-separated, segments use letters/numbers/_/-)."
        )
    return s


def load_config(path: str) -> AppConfig:
    raw = _expand_env_in_obj(_load_raw_config(path), "root")
    if not isinstance(raw, dict):
        raise ConfigError("Config root must be an object/map.")

    cosmos_raw = _as_mapping(_require(raw, "cosmos", "root"), "cosmos")
    mongo_raw = _as_mapping(_require(raw, "mongodb", "root"), "mongodb")
    collections_raw = raw.get("collections", None)
    if collections_raw is None:
        collections_raw = {}
    defaults_raw = raw.get("collection_defaults", None)
    if defaults_raw is None:
        defaults_raw = {}
    sampling_raw = raw.get("sampling", None)
    if sampling_raw is None:
        sampling_raw = {}
    logging_raw = _as_mapping(_require(raw, "logging", "root"), "logging")

    cosmos_api = _as_str(_env_nonempty("COSMOS_API") or _require(cosmos_raw, "api", "cosmos"), "cosmos.api").lower()
    cosmos_database = _as_str(
        _env_nonempty("COSMOS_DATABASE") or _require(cosmos_raw, "database", "cosmos"),
        "cosmos.database",
    )
    if cosmos_api not in {"mongo", "sql"}:
        raise ConfigError("cosmos.api must be 'mongo' or 'sql'")

    cosmos_uri = cosmos_raw.get("uri")
    cosmos_endpoint = cosmos_raw.get("endpoint")
    cosmos_key = cosmos_raw.get("key")
    if cosmos_api == "mongo":
        cosmos_uri = _as_str(
            _env_nonempty("COSMOS_URI") or _require(cosmos_raw, "uri", "cosmos"),
            "cosmos.uri",
        )
        cosmos_endpoint = None
        cosmos_key = None
    else:
        cosmos_endpoint = _as_str(
            _env_nonempty("COSMOS_ENDPOINT") or _require(cosmos_raw, "endpoint", "cosmos"),
            "cosmos.endpoint",
        )
        cosmos_key = _as_str(
            _env_nonempty("COSMOS_KEY") or _require(cosmos_raw, "key", "cosmos"),
            "cosmos.key",
        )
        cosmos_uri = None

    sampling_raw = _as_mapping(sampling_raw, "sampling")

    sampling_percentage = sampling_raw.get("percentage")
    sampling_count = sampling_raw.get("count")
    if sampling_percentage is not None and sampling_count is not None:
        raise ConfigError("sampling.percentage and sampling.count are mutually exclusive.")
    if sampling_percentage is None and sampling_count is None:
        raise ConfigError("Provide either sampling.percentage or sampling.count.")
    percentage = _as_float(sampling_percentage, "sampling.percentage") if sampling_percentage is not None else None
    if percentage is not None and (percentage <= 0 or percentage > 100):
        raise ConfigError("sampling.percentage must be >0 and <=100.")
    count = _as_int(sampling_count, "sampling.count") if sampling_count is not None else None
    if count is not None and count <= 0:
        raise ConfigError("sampling.count must be >0.")

    seed = sampling_raw.get("seed")
    if seed is not None:
        seed = _as_int(seed, "sampling.seed")

    main_log = _as_str(_require(logging_raw, "main_log", "logging"), "logging.main_log")
    output_dir = _as_str(_require(logging_raw, "output_dir", "logging"), "logging.output_dir")

    defaults_raw = _as_mapping(defaults_raw, "collection_defaults")
    defaults_enabled = defaults_raw.get("enabled", True)
    if not isinstance(defaults_enabled, bool):
        raise ConfigError("Expected boolean at collection_defaults.enabled")
    defaults_business_key_raw = defaults_raw.get("business_key", None)
    defaults_business_key = (
        _as_field_path(defaults_business_key_raw, "collection_defaults.business_key")
        if defaults_business_key_raw is not None
        else None
    )
    defaults_exclude_fields = _as_str_list(defaults_raw.get("exclude_fields"), "collection_defaults.exclude_fields")
    defaults_array_paths = _as_str_list(
        defaults_raw.get("array_order_insensitive_paths"),
        "collection_defaults.array_order_insensitive_paths",
    )
    collection_defaults = CollectionConfig(
        business_key=defaults_business_key,
        enabled=defaults_enabled,
        exclude_fields=defaults_exclude_fields,
        array_order_insensitive_paths=defaults_array_paths,
    )

    collections: dict[str, CollectionConfig] = {}
    collections_raw = _as_mapping(collections_raw, "collections")
    for name, c_raw in collections_raw.items():
        if not isinstance(name, str) or not name:
            raise ConfigError("Collection names must be non-empty strings.")
        if not isinstance(c_raw, dict):
            raise ConfigError(f"collections.{name} must be a mapping/object.")
        enabled = c_raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"Expected boolean at collections.{name}.enabled")

        if enabled:
            business_key = _as_field_path(
                _require(c_raw, "business_key", f"collections.{name}"),
                f"collections.{name}.business_key",
            )
        else:
            business_key_raw = c_raw.get("business_key", None)
            business_key = (
                _as_field_path(business_key_raw, f"collections.{name}.business_key") if business_key_raw is not None else None
            )
        exclude_fields = _as_str_list(c_raw.get("exclude_fields"), f"collections.{name}.exclude_fields")
        array_paths = _as_str_list(
            c_raw.get("array_order_insensitive_paths"),
            f"collections.{name}.array_order_insensitive_paths",
        )
        collections[name] = CollectionConfig(
            business_key=business_key,
            enabled=enabled,
            exclude_fields=exclude_fields,
            array_order_insensitive_paths=array_paths,
        )

    return AppConfig(
        cosmos=CosmosConfig(
            api=cosmos_api,
            database=cosmos_database,
            uri=cosmos_uri,
            endpoint=cosmos_endpoint,
            key=cosmos_key,
        ),
        mongodb=MongoConfig(
            uri=_as_str(_env_nonempty("MONGODB_URI") or _require(mongo_raw, "uri", "mongodb"), "mongodb.uri"),
            database=_as_str(
                _env_nonempty("MONGODB_DATABASE") or _require(mongo_raw, "database", "mongodb"),
                "mongodb.database",
            ),
        ),
        sampling=SamplingConfig(percentage=percentage, count=count, seed=seed),
        logging=LoggingConfig(main_log=main_log, output_dir=output_dir),
        collections=collections,
        collection_defaults=collection_defaults,
    )


def _load_raw_config(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return json.loads(data)
    return yaml.safe_load(data)
