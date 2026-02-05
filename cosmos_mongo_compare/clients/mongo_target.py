from __future__ import annotations

from typing import Any
from typing import Optional

from pymongo import MongoClient


class MongoTargetClient:
    def __init__(self, uri: str, database: str):
        self._client = MongoClient(uri)
        self._db = self._client[database]

    def close(self) -> None:
        self._client.close()

    def count_documents(self, collection: str) -> int:
        return int(self._db[collection].count_documents({}))

    def find_by_business_key(self, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        return self._db[collection].find_one({business_key: key_value})
