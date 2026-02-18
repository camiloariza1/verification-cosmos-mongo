from __future__ import annotations

import os
import ssl
import logging
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
_PATCHED = False


def _load_windows_system_certs(ctx: ssl.SSLContext) -> None:
    """Load certificates from the Windows certificate store into an SSLContext.

    Python's bundled OpenSSL ignores the Windows cert store by default.
    This bridges the gap so certs installed via certlm.msc are trusted.
    """
    if os.name != "nt":
        return
    try:
        import _ssl  # noqa: PLC0415

        for store_name in ("CA", "ROOT"):
            try:
                certs = _ssl.enum_certificates(store_name)  # type: ignore[attr-defined]
            except AttributeError:
                break
            for cert, _encoding, trust in certs:
                if trust is True or trust == "1.3.6.1.5.5.7.3.1":  # serverAuth OID
                    try:
                        ctx.load_verify_locations(cadata=cert if isinstance(cert, str) else None,
                                                  cafile=None)
                    except ssl.SSLError:
                        pass
                    try:
                        if isinstance(cert, bytes):
                            ctx.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(cert))
                    except (ssl.SSLError, ValueError):
                        pass
    except Exception:  # noqa: BLE001
        pass


def build_mongo_client(
    uri: str,
    *,
    force_tls12_env: str | None = None,
    logger: logging.Logger | None = None,
) -> MongoClient[Any]:
    """
    Build a PyMongo MongoClient from a URI with corporate-friendly TLS.

    Handles:
    - Loading Windows certificate store certs (corporate CAs installed via certlm.msc)
    - Reading CA bundle from REQUESTS_CA_BUNDLE / SSL_CERT_FILE env vars
    - Optionally forcing TLS 1.2 for middleboxes that reject TLS 1.3
    """
    log = logger or logging.getLogger(__name__)
    kwargs: dict[str, Any] = {}

    parsed = parse_uri(uri)
    hosts = [f"{host}:{port}" for host, port in parsed.get("nodelist", [])]
    database = parsed.get("database") or "<default>"
    option_keys = {k.lower() for k in (parsed.get("options") or {}).keys()}
    log.info(
        "Building MongoClient for hosts=%s database=%s force_tls12_env=%s",
        hosts if hosts else ["<unknown-host>"],
        database,
        force_tls12_env or "<none>",
    )

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
            log.info("Applying MongoClient tlsCAFile from environment: %s", ca_file)

    # Monkey-patch PyMongo's SSL context creation to:
    # 1. Load Windows system certs (corporate CAs from certlm.msc)
    # 2. Optionally force TLS 1.2
    force_tls12 = _env_truthy(force_tls12_env) if force_tls12_env else False
    if force_tls12:
        log.info("Forcing TLS 1.2 for MongoClient based on env var %s", force_tls12_env)

    global _PATCHED

    def get_ssl_context_patched(*args: Any, **inner_kwargs: Any):  # type: ignore[no-untyped-def]
        ctx = _ORIGINAL_GET_SSL_CONTEXT(*args, **inner_kwargs)
        _load_windows_system_certs(ctx)
        if force_tls12 and hasattr(ctx, "minimum_version") and hasattr(ssl, "TLSVersion"):
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    if not _PATCHED:
        ssl_support.get_ssl_context = get_ssl_context_patched  # type: ignore[assignment]
        _PATCHED = True

    # Ensure TLS is enabled if the URI doesn't specify it.
    if "tls" not in option_keys and "ssl" not in option_keys:
        kwargs["tls"] = True
        log.info("Enabling TLS for MongoClient because URI does not specify tls/ssl")

    client = MongoClient(uri, **kwargs)
    log.info(
        "MongoClient created for hosts=%s with kwarg keys=%s",
        hosts if hosts else ["<unknown-host>"],
        sorted(kwargs.keys()),
    )
    return client
