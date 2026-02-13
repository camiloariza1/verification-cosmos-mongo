"""Diagnostic: test raw TCP connectivity from Python to MongoDB hosts.

Usage:
    python scripts/diag_tcp.py <hostname> [port1 port2 port3]

Examples:
    python scripts/diag_tcp.py pl-0-eastus2-azure.6tu3s.mongodb.net
    python scripts/diag_tcp.py pl-0-eastus2-azure.6tu3s.mongodb.net 1024 1025 1026
"""
from __future__ import annotations

import socket
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    host = sys.argv[1]
    ports = [int(p) for p in sys.argv[2:]] if len(sys.argv) > 2 else [1024, 1025, 1026]

    print(f"Host: {host}")
    print(f"Python executable: {sys.executable}\n")

    for port in ports:
        try:
            s = socket.create_connection((host, port), timeout=10)
            print(f"Port {port}: TCP OK")
            s.close()
        except Exception as e:
            print(f"Port {port}: TCP FAIL: {e}")

    print("\nIf all TCP FAIL but Test-NetConnection works from PowerShell,")
    print("python.exe is being blocked by EDR / endpoint firewall.")
    print(f"Ask IT to allowlist: {sys.executable}")


if __name__ == "__main__":
    main()
