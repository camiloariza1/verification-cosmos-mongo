# Troubleshooting

This project is cross-platform, but most install/run issues tend to be:
- Python/venv activation confusion on Windows
- `pip` not reaching a package index (PyPI or a corporate mirror)
- Network/connectivity/auth issues to MongoDB (especially Atlas PrivateLink endpoints)

## Windows: venv activation

PowerShell:
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

cmd.exe:
```bat
py -3.13 -m venv .venv
.\.venv\Scripts\activate
```

Note: `source .venv/bin/activate` is for bash (macOS/Linux), not PowerShell/cmd.exe.

## Windows: `pip` says “No matching distribution found” / “from versions: none”

Symptoms look like:
- `ERROR: Could not find a version that satisfies the requirement ... (from versions: none)`
- failing even for common packages like `setuptools`

This almost always means `pip` cannot reach *any* index (blocked network/DNS/proxy/SSL inspection) or is configured to use `--no-index` / a private index that doesn't have your packages.

### Check you’re using the venv + correct file

```powershell
python -c "import sys; print(sys.executable)"
Get-Content .\requirements.txt
```

### Inspect `pip` config sources

```powershell
python -m pip config debug -v
```

### Check for `PIP_*` environment variables

PowerShell:
```powershell
Get-ChildItem Env:PIP*
```

cmd.exe:
```bat
set PIP
```

### Force PyPI for a single command

```powershell
python -m pip install -r .\requirements.txt --index-url https://pypi.org/simple -v
```

If that still shows `from versions: none`, you likely need a proxy or a corporate mirror.

### Proxy / corporate mirror

Check proxy env vars:
```powershell
Get-ChildItem Env:*PROXY*
```

Set (example):
```powershell
$env:HTTPS_PROXY="http://proxy.host:8080"
$env:HTTP_PROXY="http://proxy.host:8080"
```

If your org requires a package mirror:
```powershell
$env:PIP_INDEX_URL="https://your.index/simple"
```

### Offline install (wheelhouse)

On a machine with internet:
```powershell
py -3.13 -m pip download -r requirements-cosmos-sql.txt -d wheels
```

Copy the `wheels\` folder to the target machine, then install from it:
```powershell
python -m pip install --no-index --find-links .\wheels -r requirements-cosmos-sql.txt
```

## MongoDB: `ServerSelectionTimeoutError` / timeouts

If you see `pymongo.errors.ServerSelectionTimeoutError`, the tool could not reach your MongoDB server.

Common causes:
- not on the required VPN / private network
- firewall blocking outbound ports
- MongoDB Atlas IP access list not allowing your current public IP
- using a **PrivateLink-only** URI outside the private network (hostnames often start with `pl-` and use ports `1024-1026`)

### Quick connectivity tests

1) Verify which host:port pairs PyMongo will use:
```powershell
python -c "import os; from pymongo.uri_parser import parse_uri; print(parse_uri(os.environ['MONGODB_URI'])['nodelist'])"
```

2) Test the ports (replace host/ports to match your URI; PrivateLink commonly uses 1024–1026):
```powershell
Test-NetConnection <mongo-host> -Port 1024
Test-NetConnection <mongo-host> -Port 1025
Test-NetConnection <mongo-host> -Port 1026
```

3) Test a `ping` from Python with a shorter timeout:
```powershell
python -c "import os; from pymongo import MongoClient; c=MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=5000); print(c.admin.command('ping'))"
```

If Compass works but Python does not, it can be per-application firewall/EDR blocking `...\your-repo\.venv\Scripts\python.exe`.

## MongoDB: `SSL handshake failed` / WinError 10054

If you see errors like:
- `SSL handshake failed ... [WinError 10054] An existing connection was forcibly closed by the remote host`

TCP connectivity can still succeed (`Test-NetConnection` returns `TcpTestSucceeded: True`) while TLS handshakes are reset by a middlebox.

Try forcing TLS 1.2 for PyMongo (env var used by this tool):
```powershell
$env:MONGODB_FORCE_TLS12="1"
```

If you still get timeouts, you can lower timeouts to fail faster and see the detailed per-host error messages:
```powershell
$env:MONGODB_SERVER_SELECTION_TIMEOUT_MS="5000"
$env:MONGODB_CONNECT_TIMEOUT_MS="5000"
$env:MONGODB_SOCKET_TIMEOUT_MS="5000"
```

If the error persists but MongoDB Compass works from the same machine, try these URI toggles to isolate the cause:

1) Disable OCSP endpoint checking (often helps on restricted networks):
```powershell
# Append to your existing MONGODB_URI:
#   &tlsDisableOCSPEndpointCheck=true
```

2) Diagnostic only: disable TLS validation (proves whether you have a trust/CA chain issue).
```powershell
# Append to your existing MONGODB_URI:
#   &tlsInsecure=true
#
# IMPORTANT: do not use tlsInsecure=true long-term in production.
```

If `tlsInsecure=true` makes it work, fix trust properly instead:
- Ensure your system trusts the correct CA chain, or
- Provide `tlsCAFile` in the URI pointing at the required CA bundle (common in corporate SSL inspection setups).

## MongoDB: SSL handshake diagnostic (bypasses PyMongo)

If you suspect the issue is Python's TLS stack vs your network/proxy, run this
raw-socket diagnostic to **remove PyMongo from the equation entirely**:

```powershell
python -c "
import ssl, socket
host = 'pl-0-eastus2-azure.6tu3s.mongodb.net'  # replace with your host
port = 1024                                      # replace with your port

print('=== Test 1: Default context ===')
try:
    ctx = ssl.create_default_context()
    s = socket.create_connection((host, port), timeout=10)
    ss = ctx.wrap_socket(s, server_hostname=host)
    print('OK:', ss.version()); ss.close()
except Exception as e:
    print('FAIL:', e)

print('=== Test 2: TLS 1.2, no cert verify ===')
try:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    s = socket.create_connection((host, port), timeout=10)
    ss = ctx.wrap_socket(s, server_hostname=host)
    print('OK:', ss.version()); ss.close()
except Exception as e:
    print('FAIL:', e)

print('=== Test 3: TLS 1.2, no cert verify, no SNI ===')
try:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    s = socket.create_connection((host, port), timeout=10)
    ss = ctx.wrap_socket(s)
    print('OK:', ss.version()); ss.close()
except Exception as e:
    print('FAIL:', e)

print('=== Test 4: TLS 1.3, no cert verify ===')
try:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    s = socket.create_connection((host, port), timeout=10)
    ss = ctx.wrap_socket(s, server_hostname=host)
    print('OK:', ss.version()); ss.close()
except Exception as e:
    print('FAIL:', e)
"
```

**Reading the results:**

| Result | Meaning |
|--------|---------|
| All 4 FAIL with `WinError 10054` | Python's OpenSSL cannot handshake at all — a network appliance (firewall/DPI/IPS) is killing TLS on ports 1024-1026. Ask your network team to allow TLS traffic on those ports. |
| Test 1 fails, Test 2 passes | Certificate validation issue — your CA bundle is missing the required CA. Install the corporate CA via `certlm.msc` and set `REQUESTS_CA_BUNDLE`. |
| Tests with SNI fail, without SNI pass | A proxy is doing SNI-based filtering. |
| TLS 1.2 passes, TLS 1.3 fails | A middlebox doesn't support TLS 1.3. Set `MONGODB_FORCE_TLS12=1`. |
| All 4 pass | Python's TLS works fine — the issue is PyMongo-specific (raise an issue). |

## Corporate TLS inspection (CA bundle)

If your network uses a TLS inspection proxy (common in corporate environments),
Python's bundled OpenSSL does **not** automatically trust the proxy's CA.
Compass works because it uses the Windows certificate store.

### Option A — Environment variables + code support (recommended)

This tool reads `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` and passes the CA
bundle to both PyMongo (`tlsCAFile`) and the Azure Cosmos SDK (`connection_verify`).

```powershell
$env:REQUESTS_CA_BUNDLE = "C:\path\to\corporate-ca-bundle.pem"
$env:SSL_CERT_FILE      = "C:\path\to\corporate-ca-bundle.pem"
```

### Option B — Install cert into Windows store

1. Press `Win + R`, type `certlm.msc`, press Enter.
2. Right-click **Trusted Root Certification Authorities → All Tasks → Import**.
3. Import your corporate CA `.crt` or `.pem` file.

The tool automatically loads the Windows certificate store into PyMongo's SSL
context on Windows, so certs installed this way are trusted without extra env vars.

### Option C — Append to URI

```
mongodb+srv://.../?tlsCAFile=C%3A%5Cpath%5Cto%5Cca.pem
```

## Cosmos SQL/Core API: dependency check

If you’re using Cosmos SQL/Core API, confirm `azure-cosmos` is importable:
```powershell
python -c "import azure.cosmos; print('azure-cosmos ok')"
```

And make sure these are set (recommended to keep secrets out of `config.yaml`):
- `COSMOS_ENDPOINT`
- `COSMOS_KEY`
