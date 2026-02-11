from __future__ import annotations

import os
import ssl
from typing import Any

from pymongo import MongoClient
from pymongo import ssl_support


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


_ORIGINAL_GET_SSL_CONTEXT = ssl_support.get_ssl_context
_TLS12_PATCHED = False


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
        global _TLS12_PATCHED

        def get_ssl_context_tls12(*args: Any, **inner_kwargs: Any):  # type: ignore[no-untyped-def]
            ctx = _ORIGINAL_GET_SSL_CONTEXT(*args, **inner_kwargs)
            if hasattr(ctx, "minimum_version") and hasattr(ssl, "TLSVersion"):
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                ctx.maximum_version = ssl.TLSVersion.TLSv1_2
            return ctx

        if not _TLS12_PATCHED:
            ssl_support.get_ssl_context = get_ssl_context_tls12  # type: ignore[assignment]
            _TLS12_PATCHED = True

    return MongoClient(uri, **kwargs)
