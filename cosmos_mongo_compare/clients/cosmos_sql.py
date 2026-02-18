from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Iterable
from typing import Optional
from urllib.parse import urlsplit

try:
    from azure.cosmos import CosmosClient
except ImportError:  # pragma: no cover
    CosmosClient = None

from cosmos_mongo_compare.clients.base import SourceClient


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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

    def __init__(self, endpoint: str, key: str, database: str, *, logger: logging.Logger):
        if CosmosClient is None:  # pragma: no cover
            raise RuntimeError(
                "azure-cosmos is required for Cosmos SQL/Core API. "
                "Install with: python -m pip install 'azure-cosmos>=4.8.0' "
                "(Python 3.13 support starts at azure-cosmos 4.8.0)."
            )
        self._logger = logger
        host = urlsplit(endpoint).hostname or "<unknown-host>"
        self._logger.info("Creating Cosmos SQL source client for host=%s database=%s", host, database)
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
        self._logger.info("Cosmos SQL source client created for host=%s database=%s", host, database)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def list_collections(self) -> list[str]:
        return sorted([c["id"] for c in self._database.list_containers()])

    def _container(self, name: str):
        return self._database.get_container_client(name)

    def count_documents(self, collection: str) -> int:
        container = self._container(collection)
        query = "SELECT VALUE COUNT(1) FROM c"
        results = list(container.query_items(query=query, enable_cross_partition_query=True))
        return int(results[0]) if results else 0

    def sample_documents(self, *, collection: str, sample_size: int) -> list[dict]:
        """
        Cosmos SQL has no native random sampling.
        sampling.py will use deterministic key selection + point lookups when a seed is provided.

        This method intentionally raises to force the sampling layer to use seeded selection.
        """
        raise NotImplementedError("Cosmos SQL API does not support server-side random sampling.")

    def iter_business_keys(self, *, collection: str, business_key: str) -> Iterable[Any]:
        container = self._container(collection)
        expr = _sql_path_expr(business_key)
        query = f"SELECT VALUE {expr} FROM c WHERE IS_DEFINED({expr})"
        for value in container.query_items(query=query, enable_cross_partition_query=True):
            yield value

    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        container = self._container(collection)
        expr = _sql_path_expr(business_key)
        query = f"SELECT TOP 1 * FROM c WHERE {expr} = @v"
        params = [{"name": "@v", "value": key_value}]
        results = list(
            container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
                max_item_count=1,
            )
        )
        return results[0] if results else None
