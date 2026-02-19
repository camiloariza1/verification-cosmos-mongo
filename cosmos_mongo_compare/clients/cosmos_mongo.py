from __future__ import annotations

import logging
from typing import Any, Iterable
from typing import Optional
from urllib.parse import urlsplit

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from cosmos_mongo_compare.clients.base import SourceClient


class CosmosMongoSourceClient(SourceClient):
    """
    Cosmos DB (Mongo API) accessed via PyMongo.

    Notes:
    - Server-side $sample is used for non-deterministic sampling where supported.
    - Deterministic sampling (seeded) is implemented in sampling.py via iter_business_keys + find_by_business_key.
    """

    def __init__(self, uri: str, database: str, *, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)
        host = urlsplit(uri).hostname or "<unknown-host>"
        self._logger.info(
            "Creating Cosmos Mongo source client for host=%s database=%s", host, database
        )
        self._client = MongoClient(uri)
        self._logger.info("Cosmos Mongo source client created for host=%s database=%s", host, database)
        self._db = self._client[database]
        try:
            self._logger.info("Running Cosmos Mongo source ping for host=%s database=%s", host, database)
            self._client.admin.command("ping")
            self._logger.info("Cosmos Mongo source ping succeeded for host=%s database=%s", host, database)
        except PyMongoError:
            self._logger.exception("Cosmos Mongo source ping failed for host=%s database=%s", host, database)
            raise

    def close(self) -> None:
        self._client.close()

    def list_collections(self) -> list[str]:
        return sorted(self._db.list_collection_names())

    def count_documents(self, collection: str) -> int:
        return int(self._db[collection].count_documents({}))

    def sample_documents(self, *, collection: str, sample_size: int) -> list[dict]:
        pipeline = [{"$sample": {"size": int(sample_size)}}]
        return list(self._db[collection].aggregate(pipeline))

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
        self._logger.info(
            "Running Cosmos Mongo bucket sample collection=%s bucket_field=%s buckets=%s sample_size=%s",
            collection,
            bucket_field,
            bucket_values,
            sample_size,
        )
        pipeline = [
            {"$match": {bucket_field: {"$in": bucket_values}}},
            {"$sample": {"size": int(sample_size)}},
        ]
        return list(self._db[collection].aggregate(pipeline))

    def iter_business_keys(self, *, collection: str, business_key: str) -> Iterable[Any]:
        projection = {business_key: 1}
        if business_key != "_id":
            projection["_id"] = 0
        cursor = self._db[collection].find(
            {business_key: {"$exists": True}},
            projection=projection,
            batch_size=10_000,
        )
        for doc in cursor:
            yield doc.get(business_key)

    def find_by_business_key(self, *, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        return self._db[collection].find_one({business_key: key_value})
