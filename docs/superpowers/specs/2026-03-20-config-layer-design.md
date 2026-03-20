# Config Layer Design

**Date:** 2026-03-20
**Branch:** feat/api_client
**Status:** Approved

## Overview

Add a configuration layer to `nextdep_dsp` so developers can set `api_key`, `hostname`, `ssl_verify`, and `redirect` without passing them explicitly on every `DepositApi()` instantiation. Designed for dev/mock usage only.

## Architecture

A single new module — `src/nextdep_dsp/config.py` — owns all config resolution. `DepositApi.__init__` delegates to it before applying explicit constructor args on top.

Resolution order (lowest to highest priority):

1. Hardcoded defaults
2. `~/.config/nextdep/config.toml` (if it exists)
3. `ONEDEP_*` environment variables
4. Explicit constructor arguments (always win)

No new class is exposed to users — `DepositApi` works exactly as today for callers that pass explicit args.

## Config File

**Location:** `~/.config/nextdep/config.toml`

```toml
[default]
api_key = "eyJhbGci..."
hostname = "https://onedep-depui-test.wwpdb.org/deposition"
ssl_verify = false
redirect = true
```

- `[default]` profile only — structure leaves room for named profiles (e.g. `[pdbe]`) without committing to that complexity now
- File is never created automatically — developers create it manually
- TOML format chosen over YAML: stdlib support via `tomllib` (3.11+), no indentation sensitivity, no type ambiguity, designed for config

**Dependency:** add `tomli; python_version < "3.11"` for Python 3.9/3.10 support.

## Environment Variables

| Variable | Config key | Type |
|---|---|---|
| `ONEDEP_API_KEY` | `api_key` | str |
| `ONEDEP_HOSTNAME` | `hostname` | str |
| `ONEDEP_SSL_VERIFY` | `ssl_verify` | bool |
| `ONEDEP_REDIRECT` | `redirect` | bool |

`ONEDEP_API_KEY` name retained from existing documentation. All others follow the same `ONEDEP_` prefix convention.

## `config.py` Module

```python
@dataclass
class DepositConfig:
    api_key: str = ""
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True

    @classmethod
    def load(cls, **overrides) -> "DepositConfig":
        # 1. Start with dataclass defaults
        # 2. Merge config file if it exists
        # 3. Merge env vars
        # 4. Apply explicit constructor overrides
        ...
```

`DepositApi.__init__` passes only non-None constructor args as overrides:

```python
def __init__(self, hostname=None, api_key=None, ssl_verify=None, redirect=None, ...):
    config = DepositConfig.load(
        **{k: v for k, v in locals().items() if v is not None}
    )
```

All existing call sites that pass explicit args continue to work unchanged.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Config file missing | Silently skip — not an error |
| Malformed TOML | Raise `ValueError` with file path and parse error |
| Unknown keys in file | Silently ignore — forward-compatible |
| Invalid bool env var | Raise `ValueError` (accepts `true`/`false`, `1`/`0`, case-insensitive) |
| No `api_key` anywhere | Raise `DepositApiException("No API key configured...", 401)` at `DepositApi.__init__` time — fail fast before any HTTP call |

## Testing

| Test | Method |
|---|---|
| Resolution order (constructor > env > file > defaults) | `monkeypatch` + `tmp_path` config file |
| Valid TOML loads correctly | `tmp_path` fixture |
| Malformed TOML raises `ValueError` | `tmp_path` fixture |
| Bool env var coercion (`"false"` → `False`) | `monkeypatch` |
| Invalid bool env var raises `ValueError` | `monkeypatch` |
| No api_key raises `DepositApiException` at init | Direct instantiation, no HTTP mock needed |
| Existing tests unchanged | No changes required — explicit args still win |

No new test dependencies needed — `monkeypatch` and `tmp_path` are built into pytest.

## Files Changed

| File | Change |
|---|---|
| `src/nextdep_dsp/config.py` | New — `DepositConfig` dataclass + `load()` |
| `src/nextdep_dsp/deposition/deposit_api.py` | Use `DepositConfig.load()` in `__init__` |
| `pyproject.toml` | Add `tomli; python_version < "3.11"` dependency |
| `tests/test_config.py` | New — config resolution tests |
