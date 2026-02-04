from __future__ import annotations

import logging
from typing import Any, Iterable
from typing import Optional

try:
    from azure.cosmos import CosmosClient
except ImportError:  # pragma: no cover
    CosmosClient = None

from cosmos_mongo_compare.clients.base import SourceClient


class CosmosSqlSourceClient(SourceClient):
    """Cosmos DB (SQL/Core API) accessed via azure-cosmos."""

    def __init__(self, endpoint: str, key: str, database: str, *, logger: logging.Logger):
        if CosmosClient is None:  # pragma: no cover
            raise RuntimeError("azure-cosmos is required for Cosmos SQL API. Install with: pip install 'azure-cosmos>=4.5'")
        self._logger = logger
        self._client = CosmosClient(endpoint, credential=key)
        self._database = self._client.get_database_client(database)

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
        query = f"SELECT VALUE c.{business_key} FROM c WHERE IS_DEFINED(c.{business_key})"
        for value in container.query_items(query=query, enable_cross_partition_query=True):
            yield value

    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        container = self._container(collection)
        query = f"SELECT TOP 1 * FROM c WHERE c.{business_key} = @v"
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
