# Cosmos DB ↔ MongoDB Consistency Checker

Python utility to validate data consistency between:
- **Source:** Azure Cosmos DB (**Mongo API** or **SQL/Core API**)
- **Target:** MongoDB

It samples documents from the source, matches by a per-collection business key, compares documents (including nested objects/arrays), and emits:
- A main summary log (also printed to console)
- Per-collection mismatch logs (`.jsonl`)

## Install

Requirements:
- Python **3.9+** (works with **Python 3.13**)

### Windows (PowerShell)

```powershell
# Create + activate venv (explicitly use Python 3.13)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
# Note: `source .venv/bin/activate` is for bash, not PowerShell.
# If PowerShell blocks script execution, run:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Recommended (helps on newer Python versions like 3.13)
python -m pip install -U pip

# Minimal runtime deps
python -m pip install -r requirements.txt
```

### Windows (cmd.exe)

```bat
py -3.13 -m venv .venv
.\.venv\Scripts\activate

python -m pip install -U pip
python -m pip install -r requirements.txt
```

### macOS/Linux (bash/zsh)

```bash
python -m venv .venv  # if this fails, try: python3 -m venv .venv
source .venv/bin/activate

python -m pip install -U pip
python -m pip install -r requirements.txt
```

Troubleshooting (Windows / Python 3.13):
- If you see `No matching distribution found` or `from versions: none`, your `pip` is usually too old or configured to use no index / a private index.
- Try:
  - `python -m ensurepip --upgrade`
  - `python -m pip install --upgrade --isolated pip setuptools wheel`
  - `python -m pip install --isolated -r requirements.txt`
- If it still fails, check for environment variables like `PIP_NO_INDEX`, `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_FIND_LINKS`:
  - PowerShell: `Get-ChildItem Env:PIP*`
  - cmd.exe: `set PIP`
- You can also force PyPI for a single command:
  - `python -m pip install -r requirements.txt --index-url https://pypi.org/simple`

Recommended (installs the `cosmos-mongo-compare` CLI entrypoint):
```bash
python -m pip install -e .
```

If using Cosmos **SQL/Core API** (optional extra):
```bash
python -m pip install -e ".[cosmos-sql]"
```

Note: Cosmos **SQL/Core API** requires `azure-cosmos>=4.8.0` (Python 3.13 support starts at `azure-cosmos` 4.8.0).

If you are running the script directly (not `pip install -e .`), install SQL/Core deps with:
```bash
python -m pip install -r requirements-cosmos-sql.txt
```

## Configure

Start from `config.example.yaml` and set connection details and per-collection settings (copy it to e.g. `config.yaml`):
- `collections.<name>.business_key`: unique identifier used to find the same document in both systems
- `collections.<name>.enabled` (optional): set `false` to skip a collection while iterating on config (if `true`, `business_key` is required)
- `collections.<name>.exclude_fields`: fields to ignore (supports simple names and dotted paths)
- `collection_defaults` (optional): default per-collection settings used when a collection is missing from `collections` (useful with `--all-collections`)
- `sampling.percentage` or `sampling.count`
- `sampling.seed` (optional): makes sampling deterministic

Notes on choosing `business_key`:
- It must exist in both Cosmos and MongoDB for the collection, and be unique/stable.
- Cosmos **SQL/Core API** uses `id` as the built-in document identifier (there is no `_id`).
- Cosmos **Mongo API** exposes the identifier as MongoDB `_id` (even if the Azure portal shows it differently).
- If your MongoDB target uses an `ObjectId` `_id` but Cosmos uses string IDs, prefer a separate field like `id`/`memberId` and set `business_key` to that field.

### Environment variables (recommended for secrets)

The loader supports both:
- `${VARNAME}` expansion inside `config.yaml` values (e.g. `uri: "${MONGODB_URI}"`)
- Direct env overrides (if set, these take precedence over values in the config file)

Supported variables:
- `COSMOS_URI` (Cosmos **Mongo API** connection string)
- `COSMOS_ENDPOINT`, `COSMOS_KEY` (Cosmos **SQL/Core API**)
- `MONGODB_URI` (MongoDB connection string)
- `COSMOS_API`, `COSMOS_DATABASE`, `MONGODB_DATABASE` (optional convenience overrides)

Example (Windows PowerShell):
```powershell
$env:COSMOS_API="sql"
$env:COSMOS_DATABASE="source_db"
$env:COSMOS_ENDPOINT="https://account.documents.azure.com:443/"
$env:COSMOS_KEY="***"
$env:MONGODB_URI="mongodb://localhost:27017"
$env:MONGODB_DATABASE="target_db"
```

Example (Windows cmd.exe):
```bat
set COSMOS_API=sql
set COSMOS_DATABASE=source_db
set COSMOS_ENDPOINT=https://account.documents.azure.com:443/
set COSMOS_KEY=***
set MONGODB_URI=mongodb://localhost:27017
set MONGODB_DATABASE=target_db
```

## Run

On Windows, after activating the venv, the commands below work the same in PowerShell or cmd.exe. If `python` doesn't point to your venv / Python 3.13, use `py -3.13` instead.

All collections listed in config:
```text
cosmos-mongo-compare --config config.yaml
```

Example with a config under `configs/`:
```text
cosmos-mongo-compare --config configs/nlp-member.yaml
```

Single collection:
```text
cosmos-mongo-compare --config config.yaml --collection customers
```

List all Cosmos collections and compare those that have explicit config entries (if `collection_defaults` is set, it will be used for the rest):
```text
cosmos-mongo-compare --config config.yaml --all-collections
```

If you didn't install the package, you can run the script directly:
```text
python cosmos_mongo_compare.py --config config.yaml
```

## Output

- Main summary log: `logging.main_log`
- Per-collection mismatch logs: `logging.output_dir/<collection>_mismatches.jsonl`

Each mismatch record includes the source doc, target doc, and a structured list of differences with JSON paths.

## Tests

```text
python -m unittest discover -s tests -p "test_*.py"
```

Or, if you installed dev deps (`pip install -e ".[dev]"`):
```text
python -m pytest
```

## Architecture (high level)

- `cosmos_mongo_compare/clients/*`: Cosmos (Mongo/SQL) + MongoDB access
- `cosmos_mongo_compare/sampling.py`: sampling policy (server-side when possible; deterministic seeded selection otherwise)
- `cosmos_mongo_compare/compare.py`: recursive diff (missing fields, type mismatches, nested dicts, arrays)
- `cosmos_mongo_compare/reporting.py`: summary metrics + per-collection mismatch logs

## Notes / Design Decisions

- **Deterministic sampling:** when `sampling.seed` is set (or when Cosmos SQL forces it), the tool selects the `K` documents with the smallest `sha256(seed:key)` scores. This is deterministic and order-independent, but requires scanning business keys in the source collection.
- **Exclusions:** `exclude_fields` supports simple names (excluded at any depth) and dotted paths (excluded only at that path).
