from __future__ import annotations

import os
import ssl
from typing import Any

from pymongo import MongoClient
from pymongo import ssl_support
from pymongo.uri_parser import parse_uri


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


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

    parsed = parse_uri(uri)
    option_keys = {k.lower() for k in (parsed.get("options") or {}).keys()}

    # Optional env-configurable timeouts (ms).
    sst = _env_int("MONGODB_SERVER_SELECTION_TIMEOUT_MS")
    if sst is not None and "serverselectiontimeoutms" not in option_keys:
        kwargs["serverSelectionTimeoutMS"] = sst
    ct = _env_int("MONGODB_CONNECT_TIMEOUT_MS")
    if ct is not None and "connecttimeoutms" not in option_keys:
        kwargs["connectTimeoutMS"] = ct
    st = _env_int("MONGODB_SOCKET_TIMEOUT_MS")
    if st is not None and "sockettimeoutms" not in option_keys:
        kwargs["socketTimeoutMS"] = st

    # Resolve custom CA bundle for corporate TLS inspection proxies.
    # PyMongo does NOT read REQUESTS_CA_BUNDLE or SSL_CERT_FILE on its own.
    if "tlscafile" not in option_keys:
        ca_file = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
        if ca_file and os.path.isfile(ca_file):
            kwargs["tlsCAFile"] = ca_file

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

        # Ensure TLS is enabled if the URI doesn't specify it.
        if "tls" not in option_keys and "ssl" not in option_keys:
            kwargs["tls"] = True

    return MongoClient(uri, **kwargs)
