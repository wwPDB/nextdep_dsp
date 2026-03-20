# Config Layer Design

**Date:** 2026-03-20
**Branch:** feat/api_client
**Status:** Approved

## Overview

Add a configuration layer to `nextdep_dsp` so developers can set `api_key`, `hostname`, `ssl_verify`, and `redirect` without passing them explicitly on every `DepositApi()` instantiation. Although the package targets development use, env vars are supported as first-class citizens since they are the standard mechanism for injecting secrets in CI/automated pipelines.

## Architecture

A single new module — `src/nextdep_dsp/config.py` — owns all config resolution. `DepositApi.__init__` delegates to it before applying explicit constructor args on top.

Resolution order (lowest to highest priority):

1. Hardcoded defaults
2. `~/.config/nextdep/config.toml` (if it exists)
3. `ONEDEP_*` environment variables
4. Explicit constructor arguments (always win)

No new class is exposed to users — `DepositApi` works exactly as today for callers that pass explicit args. `DepositConfig` is an internal module and is not exported from the package public API.

`ver` and `logger` are intentionally excluded from the config layer — they are implementation details, not user-facing configuration.

**Behavioural change note:** This is a pre-1.0 package; semver breaking-change constraints do not apply. However, a `CHANGELOG` entry is required. The key changes:
- Callers that omit `api_key`, `ssl_verify`, or `redirect` will now get values from the config layer instead of the hardcoded defaults — this is the intended behaviour.
- Callers that previously passed `api_key=""` explicitly will now get a `DepositApiException` — intentional breaking change.
- The parameter order in `__init__` is preserved to avoid breaking positional callers.

## Config File

**Location:** `~/.config/nextdep/config.toml`

```toml
[default]
api_key = "eyJhbGci..."
hostname = "https://onedep-depui-test.wwpdb.org/deposition"
ssl_verify = false
redirect = true
```

- `[default]` is a required section name; only this section is read. Named profiles are out of scope.
- File is never created automatically — developers create it manually.
- TOML chosen over YAML: no indentation sensitivity, no type ambiguity, designed for config.
- `tomllib` is stdlib from Python 3.11+. For 3.9/3.10, add `tomli; python_version < "3.11"` as a dependency and use the conditional import pattern:

```python
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
```

## Environment Variables

| Variable | Config key | Type |
|---|---|---|
| `ONEDEP_API_KEY` | `api_key` | str |
| `ONEDEP_HOSTNAME` | `hostname` | str |
| `ONEDEP_SSL_VERIFY` | `ssl_verify` | bool |
| `ONEDEP_REDIRECT` | `redirect` | bool |

`ONEDEP_API_KEY` name retained from existing documentation. All others follow the same `ONEDEP_` prefix convention.

**Bool coercion:** accepts `"true"` / `"false"` and `"1"` / `"0"` (case-insensitive). Implemented as:

```python
def _parse_bool(value: str, var_name: str) -> bool:
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    raise ValueError(f"{var_name}={value!r} is not a valid boolean. Use 'true', 'false', '1', or '0'.")
```

Do not use `distutils.util.strtobool` — it is deprecated and removed in Python 3.12.

## `config.py` Module

`api_key` uses `Optional[str] = None` as its sentinel so "not configured" is represented as `None`, distinct from an intentionally empty string. All other fields use their hardcoded defaults directly.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class DepositConfig:
    api_key: Optional[str] = None
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True

    @classmethod
    def load(cls, **overrides) -> "DepositConfig":
        # 1. Start with dataclass defaults
        # 2. Merge config file values (if file exists and [default] section present)
        # 3. Merge env vars
        # 4. Apply caller-supplied overrides (only keys present in DepositConfig fields)
        ...
```

`DepositApi.__init__` preserves the **existing parameter order** (`hostname, api_key, ver, ssl_verify, redirect, logger`) to avoid breaking positional callers. Only non-`None` values are forwarded as overrides — this correctly passes `False` (which is not `None`) but excludes unset args:

```python
def __init__(self, hostname=None, api_key=None, ver="v1", ssl_verify=None, redirect=None, logger=None):
    overrides = {
        k: v for k, v in {"hostname": hostname, "api_key": api_key,
                           "ssl_verify": ssl_verify, "redirect": redirect}.items()
        if v is not None
    }
    config = DepositConfig.load(**overrides)
    self._hostname = config.hostname  # set explicitly before _connect
    self._api_key = config.api_key
    self._ssl_verify = config.ssl_verify
    self._redirect = config.redirect
    self._version = ver
    self._logger = logger
    self._connect(config.hostname)  # also sets self._hostname internally (harmless)
```

`_connect` guards with `if hostname:` internally, so `self._hostname` must be set before calling it — the direct assignment above ensures this.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Config file missing | Silently skip — not an error |
| Config file exists but `[default]` section absent | Silently skip — treat as empty config |
| Config file unreadable (`PermissionError`, etc.) | Propagate as-is — do not wrap |
| Malformed TOML | Raise `ValueError` with file path and parse error message |
| Unknown keys in TOML file | Silently ignore — forward-compatible |
| Empty string hostname (`ONEDEP_HOSTNAME=""` or `hostname = ""` in file) | Treat as absent — fall through to default |
| Invalid bool env var | Raise `ValueError` with accepted values listed (see `_parse_bool` above) |
| `api_key` resolves to `None` or `""` | Raise `DepositApiException("No API key configured. Set ONEDEP_API_KEY or add api_key to ~/.config/nextdep/config.toml", 401)` at `DepositApi.__init__` time — fail fast before any HTTP call |

**Note:** `ONEDEP_API_KEY=""` (empty string) is treated as absent — raises `DepositApiException`. An explicit `api_key=""` constructor arg also raises.

## Testing

| Test | Method |
|---|---|
| Resolution order: constructor > env var > file > defaults | `monkeypatch` + `tmp_path` config file |
| Valid TOML loads correctly | `tmp_path` fixture |
| Malformed TOML raises `ValueError` | `tmp_path` fixture |
| Config file present but no `[default]` section → silently skipped | `tmp_path` fixture |
| Bool env var: `"false"` → `False`, `"FALSE"` → `False`, `"0"` → `False` | `monkeypatch` |
| Bool env var: `"true"` → `True`, `"1"` → `True` | `monkeypatch` |
| Invalid bool env var raises `ValueError` | `monkeypatch` |
| `ssl_verify=False` passed explicitly is not filtered out | Direct instantiation |
| `api_key` absent → raises `DepositApiException` at init | Direct instantiation, no HTTP mock needed |
| `api_key=""` (explicit empty string) → raises `DepositApiException` | Direct instantiation |
| `ONEDEP_API_KEY=""` → raises `DepositApiException` | `monkeypatch` |
| `ONEDEP_HOSTNAME=""` → falls back to default hostname | `monkeypatch` |
| Existing tests unchanged — explicit args still override config | No test changes required |

No new test dependencies — `monkeypatch` and `tmp_path` are built into pytest.

## Files Changed

| File | Change |
|---|---|
| `src/nextdep_dsp/config.py` | New — `DepositConfig` dataclass + `load()` + `_parse_bool()` |
| `src/nextdep_dsp/deposition/deposit_api.py` | Use `DepositConfig.load()` in `__init__`; preserve existing parameter order |
| `pyproject.toml` | Add `tomli; python_version < "3.11"` dependency |
| `tests/test_config.py` | New — config resolution and edge case tests |
| `CHANGELOG` | Document breaking change: `api_key=""` now raises; config layer governs unset args |
