from __future__ import annotations

from typing import Any
from typing import Optional

from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from cosmos_mongo_compare.clients.mongo_client_factory import build_mongo_client


class MongoTargetClient:
    def __init__(self, uri: str, database: str):
        self._client = build_mongo_client(uri, force_tls12_env="MONGODB_FORCE_TLS12")
        self._db = self._client[database]
        try:
            self._client.admin.command("ping")
        except ServerSelectionTimeoutError as exc:
            raise RuntimeError(
                "Unable to connect to target MongoDB (timed out). "
                "Check MONGODB_URI and network access (VPN/firewall/IP allowlist). "
                "If your host starts with 'pl-' and ports are 1024-1026, it's likely a PrivateLink-only endpoint. "
                f"Details: {exc}"
            ) from exc
        except OperationFailure as exc:
            raise RuntimeError(
                "Connected to target MongoDB, but authentication/authorization failed. "
                "Check username/password, authSource, and user permissions in MONGODB_URI."
            ) from exc

    def close(self) -> None:
        self._client.close()

    def count_documents(self, collection: str) -> int:
        return int(self._db[collection].count_documents({}))

    def find_by_business_key(self, collection: str, business_key: str, key_value: Any) -> Optional[dict]:
        return self._db[collection].find_one({business_key: key_value})
