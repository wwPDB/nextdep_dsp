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

**Behavioural change note:** The existing `DepositApi.__init__` defaults are `api_key=""`, `ssl_verify=True`, `redirect=True`. After this change, callers that omit these args will get values from the config layer instead of the hardcoded defaults. This is the intended behaviour. Callers that previously relied on passing `api_key=""` explicitly (e.g. for unauthenticated use) will now get a `DepositApiException` — this is an intentional breaking change.

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
        # 2. Merge config file values (if file exists)
        # 3. Merge env vars
        # 4. Apply caller-supplied overrides
        # Unknown keys in overrides are silently ignored
        ...
```

`DepositApi.__init__` passes only the known config keys that the caller explicitly set (not `None`). `ver` and `logger` are excluded from the overrides dict:

```python
def __init__(self, hostname=None, api_key=None, ssl_verify=None, redirect=None, ver="v1", logger=None):
    overrides = {
        k: v for k, v in {"hostname": hostname, "api_key": api_key,
                           "ssl_verify": ssl_verify, "redirect": redirect}.items()
        if v is not None
    }
    config = DepositConfig.load(**overrides)
    self._api_key = config.api_key
    self._ssl_verify = config.ssl_verify
    self._redirect = config.redirect
    self._version = ver
    self._logger = logger
    self._connect(config.hostname)  # sets self._hostname internally
```

`_connect` sets `self._hostname` internally — do not set `self._hostname` before calling `_connect` to avoid a redundant double-assignment.

All existing call sites that pass explicit args continue to work unchanged.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Config file missing | Silently skip — not an error |
| Config file exists but `[default]` section absent | Silently skip — treat as empty config |
| Config file unreadable (`PermissionError`, etc.) | Propagate as-is — do not wrap |
| Malformed TOML | Raise `ValueError` with file path and parse error message |
| Unknown keys in file | Silently ignore — forward-compatible |
| Invalid bool env var | Raise `ValueError` with accepted values listed (see `_parse_bool` above) |
| `api_key` resolves to `""` or is absent | Raise `DepositApiException("No API key configured. Set ONEDEP_API_KEY or add api_key to ~/.config/nextdep/config.toml", 401)` at `DepositApi.__init__` time — fail fast before any HTTP call |

**Note:** `ONEDEP_API_KEY=""` (empty string) is treated the same as absent — raises `DepositApiException`. An explicit `api_key=""` constructor arg also raises.

## Testing

| Test | Method |
|---|---|
| Resolution order: constructor > env var > file > defaults | `monkeypatch` + `tmp_path` config file |
| Valid TOML loads correctly | `tmp_path` fixture |
| Malformed TOML raises `ValueError` | `tmp_path` fixture |
| Bool env var: `"false"` → `False`, `"FALSE"` → `False`, `"0"` → `False` | `monkeypatch` |
| Bool env var: `"true"` → `True`, `"1"` → `True` | `monkeypatch` |
| Invalid bool env var raises `ValueError` | `monkeypatch` |
| `api_key` absent → raises `DepositApiException` at init | Direct instantiation, no HTTP mock needed |
| `api_key=""` (explicit empty string) → raises `DepositApiException` | Direct instantiation |
| `ONEDEP_API_KEY=""` → raises `DepositApiException` | `monkeypatch` |
| Existing tests unchanged — explicit args still override config | No test changes required |

No new test dependencies — `monkeypatch` and `tmp_path` are built into pytest.

## Files Changed

| File | Change |
|---|---|
| `src/nextdep_dsp/config.py` | New — `DepositConfig` dataclass + `load()` + `_parse_bool()` |
| `src/nextdep_dsp/deposition/deposit_api.py` | Use `DepositConfig.load()` in `__init__`; assign fields from config object |
| `pyproject.toml` | Add `tomli; python_version < "3.11"` dependency |
| `tests/test_config.py` | New — config resolution and edge case tests |
