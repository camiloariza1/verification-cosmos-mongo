from __future__ import annotations

import logging
from typing import Any
from typing import Optional
from urllib.parse import urlsplit

from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from cosmos_mongo_compare.clients.mongo_client_factory import build_mongo_client


class MongoTargetClient:
    def __init__(self, uri: str, database: str, *, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)
        host = urlsplit(uri).hostname or "<unknown-host>"
        self._logger.info(
            "Creating target MongoDB client for host=%s database=%s", host, database
        )
        self._client = build_mongo_client(uri, force_tls12_env="MONGODB_FORCE_TLS12", logger=self._logger)
        self._logger.info("Target MongoDB client created for host=%s database=%s", host, database)
        self._db = self._client[database]
        try:
            self._logger.info("Running target MongoDB ping for host=%s database=%s", host, database)
            self._client.admin.command("ping")
            self._logger.info("Target MongoDB ping succeeded for host=%s database=%s", host, database)
        except ServerSelectionTimeoutError as exc:
            self._logger.exception("Target MongoDB ping timed out for host=%s database=%s", host, database)
            raise RuntimeError(
                "Unable to connect to target MongoDB (timed out). "
                "Check MONGODB_URI and network access (VPN/firewall/IP allowlist). "
                "If your host starts with 'pl-' and ports are 1024-1026, it's likely a PrivateLink-only endpoint. "
                f"Details: {exc}"
            ) from exc
        except OperationFailure as exc:
            self._logger.exception(
                "Target MongoDB ping failed with auth/authorization error for host=%s database=%s",
                host,
                database,
            )
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
