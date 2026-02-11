from __future__ import annotations

import os
import ssl
from typing import Any

from pymongo import MongoClient
from pymongo.uri_parser import parse_uri


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def build_mongo_client(uri: str, *, force_tls12_env: str | None = None) -> MongoClient[Any]:
    """
    Build a PyMongo MongoClient from a URI, optionally forcing TLS 1.2.

    Why this exists:
    - Some environments (certain VPNs / middleboxes) reset TLS 1.3 handshakes.
      Forcing TLS 1.2 can make PyMongo behave more like Compass and succeed.
    """
    kwargs: dict[str, Any] = {}

    force_tls12 = _env_truthy(force_tls12_env) if force_tls12_env else False
    if force_tls12:
        ssl_context = ssl.create_default_context()
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ssl_context

        # Only set tls=True if the URI does not explicitly specify TLS/SSL.
        # (Avoids ConfigurationError due to duplicate/conflicting options.)
        parsed = parse_uri(uri)
        options = {k.lower() for k in (parsed.get("options") or {}).keys()}
        if "tls" not in options and "ssl" not in options:
            kwargs["tls"] = True

    return MongoClient(uri, **kwargs)

