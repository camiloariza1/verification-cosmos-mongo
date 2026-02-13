"""Diagnostic: test TLS handshake from Python to MongoDB hosts.

Runs 4 tests with different TLS configurations to isolate the failure.

Usage:
    python scripts/diag_tls.py <hostname> [port]

Examples:
    python scripts/diag_tls.py pl-0-eastus2-azure.6tu3s.mongodb.net
    python scripts/diag_tls.py pl-0-eastus2-azure.6tu3s.mongodb.net 1024
"""
from __future__ import annotations

import socket
import ssl
import sys


def _test(label: str, host: str, port: int, ctx: ssl.SSLContext, *, use_sni: bool = True) -> None:
    print(f"=== {label} ===")
    try:
        s = socket.create_connection((host, port), timeout=10)
        ss = ctx.wrap_socket(s, server_hostname=host if use_sni else None)
        print(f"  OK: {ss.version()}")
        ss.close()
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1024

    print(f"Host: {host}:{port}")
    print(f"OpenSSL: {ssl.OPENSSL_VERSION}")
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}\n")

    # Test 1: Default context
    ctx = ssl.create_default_context()
    _test("Test 1: Default context", host, port, ctx)

    # Test 2: TLS 1.2, no cert verify
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    _test("Test 2: TLS 1.2, no cert verify", host, port, ctx)

    # Test 3: TLS 1.2, no cert verify, no SNI
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    _test("Test 3: TLS 1.2, no cert verify, no SNI", host, port, ctx, use_sni=False)

    # Test 4: TLS 1.3, no cert verify
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    _test("Test 4: TLS 1.3, no cert verify", host, port, ctx)

    print()
    print("Result guide:")
    print("  All FAIL (timed out)  -> python.exe is blocked by EDR/firewall (not a code issue)")
    print("  All FAIL (WinError)   -> network appliance killing TLS on these ports")
    print("  Test 1 fail, 2 pass   -> CA certificate issue (set REQUESTS_CA_BUNDLE)")
    print("  TLS 1.2 pass, 1.3 no  -> middlebox issue (set MONGODB_FORCE_TLS12=1)")
    print("  All pass              -> Python TLS works, issue is PyMongo-specific")


if __name__ == "__main__":
    main()
