from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Iterable
from typing import Optional
from urllib.parse import urlsplit

try:
    from azure.cosmos import CosmosClient
except ImportError:  # pragma: no cover
    CosmosClient = None
try:
    from azure.cosmos.exceptions import CosmosHttpResponseError
except ImportError:  # pragma: no cover
    CosmosHttpResponseError = None

from cosmos_mongo_compare.clients.base import SourceClient


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_POINT_LOOKUP_LOG_EVERY = 1000


def _sql_path_expr(field_path: str) -> str:
    expr = "c"
    for segment in field_path.split("."):
        if _IDENTIFIER_RE.fullmatch(segment) is not None:
            expr = f"{expr}.{segment}"
        else:
            expr = f"{expr}[{json.dumps(segment)}]"
    return expr


class CosmosSqlSourceClient(SourceClient):
    """Cosmos DB (SQL/Core API) accessed via azure-cosmos."""

    def __init__(
        self,
        endpoint: str,
        key: str,
        database: str,
        *,
        logger: logging.Logger,
        retry_max_attempts: int = 6,
        retry_base_delay_ms: int = 500,
    ):
        if CosmosClient is None:  # pragma: no cover
            raise RuntimeError(
                "azure-cosmos is required for Cosmos SQL/Core API. "
                "Install with: python -m pip install 'azure-cosmos>=4.8.0' "
                "(Python 3.13 support starts at azure-cosmos 4.8.0)."
            )
        self._logger = logger
        self._host = urlsplit(endpoint).hostname or "<unknown-host>"
        self._database_name = database
        self._point_lookup_calls = 0
        self._point_lookup_found = 0
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay_ms = retry_base_delay_ms
        self._container_cache: dict[str, Any] = {}
        self._logger.info("Creating Cosmos SQL source client for host=%s database=%s", self._host, database)
        # Pass corporate CA bundle so azure-cosmos/requests trusts the proxy cert.
        ca_file = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
        cosmos_kwargs: dict[str, Any] = {}
        if ca_file and os.path.isfile(ca_file):
            cosmos_kwargs["connection_verify"] = ca_file
            self._logger.info("Using CA bundle for Cosmos SQL source client: %s", ca_file)
        else:
            self._logger.info("No custom CA bundle found for Cosmos SQL source client")
        self._client = CosmosClient(endpoint, credential=key, **cosmos_kwargs)
        self._database = self._client.get_database_client(database)
        self._logger.info("Cosmos SQL source client created for host=%s database=%s", self._host, database)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def list_collections(self) -> list[str]:
        self._logger.info(
            "Listing Cosmos SQL containers for host=%s database=%s",
            self._host,
            self._database_name,
        )
        try:
            names = sorted([c["id"] for c in self._database.list_containers()])
            self._logger.info(
                "Listed Cosmos SQL containers for host=%s database=%s count=%s",
                self._host,
                self._database_name,
                len(names),
            )
            return names
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Failed listing Cosmos SQL containers for host=%s database=%s",
                self._host,
                self._database_name,
            )
            raise

    def _container(self, name: str):
        existing = self._container_cache.get(name)
        if existing is not None:
            return existing
        self._logger.info(
            "Creating Cosmos SQL container client host=%s database=%s container=%s",
            self._host,
            self._database_name,
            name,
        )
        container = self._database.get_container_client(name)
        self._container_cache[name] = container
        return container

    def _query_items_with_retry(
        self,
        *,
        container: Any,
        query: str,
        operation: str,
        parameters: Optional[list[dict[str, Any]]] = None,
        max_item_count: Optional[int] = None,
    ) -> list[Any]:
        for attempt in range(1, self._retry_max_attempts + 1):
            try:
                kwargs: dict[str, Any] = {
                    "query": query,
                    "enable_cross_partition_query": True,
                }
                if parameters is not None:
                    kwargs["parameters"] = parameters
                if max_item_count is not None:
                    kwargs["max_item_count"] = max_item_count
                return list(
                    container.query_items(**kwargs)
                )
            except Exception as exc:  # noqa: BLE001
                is_429 = (
                    CosmosHttpResponseError is not None
                    and isinstance(exc, CosmosHttpResponseError)
                    and getattr(exc, "status_code", None) == 429
                )
                if not is_429 or attempt >= self._retry_max_attempts:
                    raise
                headers = getattr(exc, "headers", {}) or {}
                retry_after_ms = headers.get("x-ms-retry-after-ms")
                if retry_after_ms is not None:
                    try:
                        delay_seconds = max(0.0, float(retry_after_ms) / 1000.0)
                    except ValueError:
                        delay_seconds = 0.0
                else:
                    delay_seconds = max(0.0, (self._retry_base_delay_ms / 1000.0) * (2 ** (attempt - 1)))
                self._logger.warning(
                    "Cosmos SQL %s throttled with 429 host=%s database=%s attempt=%s/%s retry_delay_seconds=%.3f",
                    operation,
                    self._host,
                    self._database_name,
                    attempt,
                    self._retry_max_attempts,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
        return []

    def count_documents(self, collection: str) -> int:
        container = self._container(collection)
        query = "SELECT VALUE COUNT(1) FROM c"
        self._logger.info(
            "Running Cosmos SQL count query host=%s database=%s container=%s",
            self._host,
            self._database_name,
            collection,
        )
        try:
            results = self._query_items_with_retry(
                container=container,
                query=query,
                operation=f"count query container={collection}",
            )
            count = int(results[0]) if results else 0
            self._logger.info(
                "Cosmos SQL count query succeeded host=%s database=%s container=%s count=%s",
                self._host,
                self._database_name,
                collection,
                count,
            )
            return count
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Cosmos SQL count query failed host=%s database=%s container=%s query=%s",
                self._host,
                self._database_name,
                collection,
                query,
            )
            raise

    def sample_documents(self, *, collection: str, sample_size: int) -> list[dict]:
        container = self._container(collection)
        query = f"SELECT TOP {int(sample_size)} * FROM c"
        self._logger.info(
            "Running Cosmos SQL fast sample query host=%s database=%s container=%s sample_size=%s",
            self._host,
            self._database_name,
            collection,
            sample_size,
        )
        try:
            return self._query_items_with_retry(
                container=container,
                query=query,
                operation=f"fast sample query container={collection}",
                max_item_count=sample_size,
            )
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Cosmos SQL fast sample query failed host=%s database=%s container=%s query=%s",
                self._host,
                self._database_name,
                collection,
                query,
            )
            raise

    def sample_documents_by_buckets(
        self,
        *,
        collection: str,
        bucket_field: str,
        bucket_values: list[int],
        sample_size: int,
    ) -> list[dict]:
        if not bucket_values or sample_size <= 0:
            return []
        container = self._container(collection)
        expr = _sql_path_expr(bucket_field)
        terms = []
        params: list[dict[str, Any]] = []
        for idx, bucket_value in enumerate(bucket_values):
            pname = f"@b{idx}"
            terms.append(f"{expr} = {pname}")
            params.append({"name": pname, "value": bucket_value})
        query = f"SELECT TOP {int(sample_size)} * FROM c WHERE IS_DEFINED({expr}) AND ({' OR '.join(terms)})"
        self._logger.info(
            "Running Cosmos SQL bucket sample query host=%s database=%s container=%s bucket_field=%s buckets=%s sample_size=%s",
            self._host,
            self._database_name,
            collection,
            bucket_field,
            bucket_values,
            sample_size,
        )
        try:
            return self._query_items_with_retry(
                container=container,
                query=query,
                parameters=params,
                operation=f"bucket sample query container={collection}",
                max_item_count=sample_size,
            )
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Cosmos SQL bucket sample query failed host=%s database=%s container=%s bucket_field=%s query=%s",
                self._host,
                self._database_name,
                collection,
                bucket_field,
                query,
            )
            raise

    def iter_business_keys(self, *, collection: str, business_key: str) -> Iterable[Any]:
        container = self._container(collection)
        expr = _sql_path_expr(business_key)
        query = f"SELECT VALUE {expr} FROM c WHERE IS_DEFINED({expr})"
        self._logger.info(
            "Running Cosmos SQL business-key query host=%s database=%s container=%s business_key=%s",
            self._host,
            self._database_name,
            collection,
            business_key,
        )
        try:
            for value in container.query_items(query=query, enable_cross_partition_query=True):
                yield value
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Cosmos SQL business-key query failed host=%s database=%s container=%s business_key=%s query=%s",
                self._host,
                self._database_name,
                collection,
                business_key,
                query,
            )
            raise

    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        container = self._container(collection)
        expr = _sql_path_expr(business_key)
        query = f"SELECT TOP 1 * FROM c WHERE {expr} = @v"
        params = [{"name": "@v", "value": key_value}]
        try:
            results = self._query_items_with_retry(
                container=container,
                query=query,
                parameters=params,
                operation=f"point lookup container={collection}",
                max_item_count=1,
            )
            found = bool(results)
            self._point_lookup_calls += 1
            if found:
                self._point_lookup_found += 1
            if self._point_lookup_calls % _POINT_LOOKUP_LOG_EVERY == 0:
                self._logger.info(
                    "Cosmos SQL point lookup progress host=%s database=%s container=%s business_key=%s lookups=%s found=%s",
                    self._host,
                    self._database_name,
                    collection,
                    business_key,
                    self._point_lookup_calls,
                    self._point_lookup_found,
                )
            return results[0] if results else None
        except Exception:  # noqa: BLE001
            self._logger.exception(
                "Cosmos SQL point lookup failed host=%s database=%s container=%s business_key=%s query=%s",
                self._host,
                self._database_name,
                collection,
                business_key,
                query,
            )
            raise
