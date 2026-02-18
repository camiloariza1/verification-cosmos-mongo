from __future__ import annotations

import logging
import os
import socket
import time
from typing import Any
from typing import Optional
from urllib.parse import urlsplit

from pymongo.uri_parser import parse_uri
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from cosmos_mongo_compare.clients.mongo_client_factory import build_mongo_client


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _log_target_preflight(uri: str, logger: logging.Logger) -> None:
    try:
        parsed = parse_uri(uri)
        nodes = parsed.get("nodelist", [])
    except Exception:  # noqa: BLE001
        logger.exception("Failed to parse MONGODB_URI during preflight")
        return

    if not nodes:
        logger.warning("Target MongoDB preflight found no host:port nodes in URI")
        return

    timeout_ms = _env_int("MONGODB_CONNECT_TIMEOUT_MS") or 5000
    timeout_seconds = timeout_ms / 1000.0

    logger.info(
        "Target MongoDB preflight starting for nodes=%s timeout_ms=%s",
        [f"{host}:{port}" for host, port in nodes],
        timeout_ms,
    )
    for host, port in nodes:
        logger.info("Preflight DNS lookup for target MongoDB node=%s:%s", host, port)
        try:
            resolved = sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
            logger.info("Preflight DNS resolved node=%s:%s addresses=%s", host, port, resolved)
        except Exception:  # noqa: BLE001
            logger.exception("Preflight DNS lookup failed for target MongoDB node=%s:%s", host, port)
            continue

        logger.info("Preflight TCP connect for target MongoDB node=%s:%s timeout_ms=%s", host, port, timeout_ms)
        started = time.monotonic()
        try:
            sock = socket.create_connection((host, port), timeout=timeout_seconds)
            sock.close()
            elapsed_ms = round((time.monotonic() - started) * 1000)
            logger.info("Preflight TCP connect succeeded for target MongoDB node=%s:%s elapsed_ms=%s", host, port, elapsed_ms)
        except Exception:  # noqa: BLE001
            elapsed_ms = round((time.monotonic() - started) * 1000)
            logger.exception(
                "Preflight TCP connect failed for target MongoDB node=%s:%s elapsed_ms=%s",
                host,
                port,
                elapsed_ms,
            )


class MongoTargetClient:
    def __init__(self, uri: str, database: str, *, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)
        host = urlsplit(uri).hostname or "<unknown-host>"
        self._logger.info(
            "Creating target MongoDB client for host=%s database=%s", host, database
        )
        _log_target_preflight(uri, self._logger)
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
