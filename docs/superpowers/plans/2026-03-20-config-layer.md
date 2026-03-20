# Config Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a layered configuration system to `DepositApi` so developers can set `api_key`, `hostname`, `ssl_verify`, and `redirect` via a TOML file or environment variables instead of passing them on every instantiation.

**Architecture:** A new `src/nextdep_dsp/config.py` module owns all resolution logic with priority: constructor args > env vars > `~/.config/nextdep/config.toml` > hardcoded defaults. `DepositApi.__init__` calls `DepositConfig.load()` and fails fast with `DepositApiException` if no `api_key` is configured anywhere.

**Tech Stack:** Python 3.9+, `tomllib` (stdlib 3.11+) / `tomli` backport (3.9–3.10), `pytest` with `monkeypatch` and `tmp_path` fixtures, existing `DepositApiException`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/nextdep_dsp/config.py` | **Create** | `DepositConfig` dataclass, `load()` classmethod, `_parse_bool()` helper |
| `tests/test_config.py` | **Create** | All config resolution and edge-case tests (top-level, alongside `test_nextdep_dsp.py`) |
| `src/nextdep_dsp/deposition/deposit_api.py` | **Modify** | Wire `DepositConfig.load()` into `__init__`; add fail-fast api_key guard |
| `tests/tests/test_deposit_api.py` | **Modify** | Fix `MyDepositApi` fixture: add dummy `api_key` to avoid new fail-fast |
| `pyproject.toml` | **Modify** | Add `tomli; python_version < "3.11"` dependency |
| `CHANGELOG/v0.1.0.md` | **Modify** | Document breaking change |

> **Important:** `DepositConfig` must NOT be imported into `src/nextdep_dsp/__init__.py`. It is an internal module only.

---

## Task 1: Add `tomli` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, find the `[project]` `dependencies` list and add:

```toml
dependencies = [
  "requests>=2.32.5",
  "rich",
  "typer",
  "tomli; python_version < '3.11'",
]
```

- [ ] **Step 2: Sync the environment**

```bash
uv sync
```

Expected: resolves and installs `tomli` on Python < 3.11, no-op on 3.11+.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add tomli backport for Python 3.9/3.10 TOML support"
```

---

## Task 2: Create `config.py` — `_parse_bool` and `DepositConfig` skeleton

**Files:**
- Create: `src/nextdep_dsp/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for `_parse_bool`**

Create `tests/test_config.py`:

```python
import pytest
from nextdep_dsp.config import _parse_bool


def test_parse_bool_true_values():
    assert _parse_bool("true", "VAR") is True
    assert _parse_bool("True", "VAR") is True
    assert _parse_bool("TRUE", "VAR") is True
    assert _parse_bool("1", "VAR") is True


def test_parse_bool_false_values():
    assert _parse_bool("false", "VAR") is False
    assert _parse_bool("False", "VAR") is False
    assert _parse_bool("FALSE", "VAR") is False
    assert _parse_bool("0", "VAR") is False


def test_parse_bool_invalid_raises():
    with pytest.raises(ValueError, match="ONEDEP_SSL_VERIFY"):
        _parse_bool("yes", "ONEDEP_SSL_VERIFY")
    with pytest.raises(ValueError, match="ONEDEP_REDIRECT"):
        _parse_bool("on", "ONEDEP_REDIRECT")
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: `ImportError` — `nextdep_dsp.config` does not exist yet.

- [ ] **Step 3: Create `config.py` with `_parse_bool` only**

```python
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_CONFIG_FILE = Path.home() / ".config" / "nextdep" / "config.toml"


def _parse_bool(value: str, var_name: str) -> bool:
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    raise ValueError(
        f"{var_name}={value!r} is not a valid boolean. Use 'true', 'false', '1', or '0'."
    )


@dataclass
class DepositConfig:
    api_key: Optional[str] = None
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True

    @classmethod
    def load(cls, **overrides) -> "DepositConfig":
        return cls()  # placeholder — wired up in Task 3
```

- [ ] **Step 4: Run tests to verify `_parse_bool` passes**

```bash
pytest tests/test_config.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nextdep_dsp/config.py tests/test_config.py
git commit -m "feat: add config module skeleton with _parse_bool"
```

---

## Task 3: Implement `DepositConfig.load()` — config file layer

**Files:**
- Modify: `src/nextdep_dsp/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for TOML file loading**

Add to `tests/test_config.py`:

```python
from nextdep_dsp.config import DepositConfig


def test_load_defaults_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"
    assert config.ssl_verify is True
    assert config.redirect is True
    assert config.api_key is None


def test_load_reads_toml_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "mykey"\nhostname = "https://example.com"\nssl_verify = false\nredirect = false\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key == "mykey"
    assert config.hostname == "https://example.com"
    assert config.ssl_verify is False
    assert config.redirect is False


def test_load_skips_missing_default_section(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[other]\napi_key = "ignored"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key is None  # [default] absent → skipped


def test_load_malformed_toml_raises(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("this is not : valid toml [[\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="config.toml"):
        DepositConfig.load()


def test_load_ignores_unknown_keys_in_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "mykey"\nunknown_key = "ignored"\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key == "mykey"  # did not raise


def test_load_empty_hostname_in_file_falls_back(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[default]\nhostname = ""\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_config.py -v -k "toml or default_section or malformed or unknown_keys"
```

Expected: FAIL — `load()` is still a placeholder.

- [ ] **Step 3: Implement the file-reading layer in `load()`**

Replace the `load()` classmethod in `config.py`:

```python
@classmethod
def load(cls, **overrides) -> "DepositConfig":
    valid_fields = {f.name for f in fields(cls)}
    merged: dict = {}

    # Layer 1: config file
    config_file = Path.home() / ".config" / "nextdep" / "config.toml"
    if config_file.exists():
        try:
            with open(config_file, "rb") as fp:
                raw = tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            # Only catch parse errors; PermissionError/OSError propagate as-is (per spec)
            raise ValueError(f"Failed to parse {config_file}: {exc}") from exc
        section = raw.get("default", {})
        for key, value in section.items():
            if key in valid_fields:
                # Empty-string hostname in file is treated as absent
                if key == "hostname" and value == "":
                    continue
                merged[key] = value

    # Layer 2: env vars (applied in Task 4)

    # Layer 3: caller overrides
    for key, value in overrides.items():
        if key in valid_fields:
            merged[key] = value

    return cls(**merged)
```

- [ ] **Step 4: Run tests to verify file layer passes**

```bash
pytest tests/test_config.py -v
```

Expected: all tests PASS (env var tests not written yet, existing tests still pass).

- [ ] **Step 5: Commit**

```bash
git add src/nextdep_dsp/config.py tests/test_config.py
git commit -m "feat: implement DepositConfig.load() with TOML file support"
```

---

## Task 4: Add env var layer to `DepositConfig.load()`

**Files:**
- Modify: `src/nextdep_dsp/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing env var tests**

Add to `tests/test_config.py`:

```python
def test_env_var_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load()
    assert config.api_key == "env-key"


def test_env_var_hostname(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_HOSTNAME", "https://env.example.com")
    config = DepositConfig.load()
    assert config.hostname == "https://env.example.com"


def test_env_var_empty_hostname_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_HOSTNAME", "")
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"


def test_env_var_ssl_verify_false(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "key")
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "false")
    config = DepositConfig.load()
    assert config.ssl_verify is False


def test_env_var_ssl_verify_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "FALSE")
    config = DepositConfig.load()
    assert config.ssl_verify is False


def test_env_var_redirect_false(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_REDIRECT", "0")
    config = DepositConfig.load()
    assert config.redirect is False


def test_env_var_invalid_bool_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "yes")
    with pytest.raises(ValueError, match="ONEDEP_SSL_VERIFY"):
        DepositConfig.load()


def test_env_var_overrides_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[default]\napi_key = "file-key"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load()
    assert config.api_key == "env-key"


def test_constructor_overrides_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load(api_key="explicit-key")
    assert config.api_key == "explicit-key"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_config.py -v -k "env_var"
```

Expected: FAIL — env vars not read yet.

- [ ] **Step 3: Replace `load()` with the complete implementation including env var layer**

Replace the entire `load()` classmethod in `config.py` with this final version:

```python
_ENV_MAP = {
    "ONEDEP_API_KEY": ("api_key", str),
    "ONEDEP_HOSTNAME": ("hostname", str),
    "ONEDEP_SSL_VERIFY": ("ssl_verify", lambda v: _parse_bool(v, "ONEDEP_SSL_VERIFY")),
    "ONEDEP_REDIRECT": ("redirect", lambda v: _parse_bool(v, "ONEDEP_REDIRECT")),
}


@classmethod
def load(cls, **overrides) -> "DepositConfig":
    valid_fields = {f.name for f in fields(cls)}
    merged: dict = {}

    # Layer 1: config file
    config_file = Path.home() / ".config" / "nextdep" / "config.toml"
    if config_file.exists():
        try:
            with open(config_file, "rb") as fp:
                raw = tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Failed to parse {config_file}: {exc}") from exc
        section = raw.get("default", {})
        for key, value in section.items():
            if key in valid_fields:
                if key == "hostname" and value == "":
                    continue
                merged[key] = value

    # Layer 2: env vars
    for env_var, (field_name, coerce) in _ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is not None:
            value = coerce(raw)
            if field_name == "hostname" and value == "":
                continue
            merged[field_name] = value

    # Layer 3: caller overrides (only known fields)
    for key, value in overrides.items():
        if key in valid_fields:
            merged[key] = value

    return cls(**merged)
```

> Note: `_ENV_MAP` is defined at class body level (not inside `load()`), so it is constructed once rather than on every call.

- [ ] **Step 4: Run all config tests**

```bash
pytest tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nextdep_dsp/config.py tests/test_config.py
git commit -m "feat: add env var layer to DepositConfig.load()"
```

---

## Task 5: Wire `DepositConfig.load()` into `DepositApi.__init__`

**Files:**
- Modify: `src/nextdep_dsp/deposition/deposit_api.py`
- Modify: `tests/tests/test_deposit_api.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing integration tests**

Add to `tests/test_config.py`:

```python
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.exceptions import DepositApiException


def test_deposit_api_raises_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com")


def test_deposit_api_raises_with_empty_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com", api_key="")


def test_deposit_api_raises_with_empty_env_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "")
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com")


def test_deposit_api_ssl_verify_false_not_filtered(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    api = DepositApi(hostname="https://example.com", api_key="key", ssl_verify=False)
    assert api._ssl_verify is False


def test_deposit_api_uses_config_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "file-key"\nhostname = "https://file.example.com"\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    api = DepositApi()
    assert api._api_key == "file-key"
    assert api._hostname == "https://file.example.com"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_config.py -v -k "deposit_api"
```

Expected: FAIL — `DepositApi.__init__` doesn't call `DepositConfig.load()` yet.

- [ ] **Step 3: Update `DepositApi.__init__`**

In `src/nextdep_dsp/deposition/deposit_api.py`, add the import at the top:

```python
from nextdep_dsp.config import DepositConfig
from nextdep_dsp.deposition.exceptions import DepositApiException
```

Then replace the existing `__init__` method body (keep the same signature — parameter order must not change):

```python
def __init__(
    self,
    hostname: str = None,
    api_key: str = None,
    ver: str = "v1",
    ssl_verify: bool = None,
    redirect: bool = None,
    logger: logging.Logger = None,
):
    overrides = {
        k: v
        for k, v in {
            "hostname": hostname,
            "api_key": api_key,
            "ssl_verify": ssl_verify,
            "redirect": redirect,
        }.items()
        if v is not None
    }
    config = DepositConfig.load(**overrides)

    if not config.api_key:
        raise DepositApiException(
            "No API key configured. Set ONEDEP_API_KEY or add api_key to ~/.config/nextdep/config.toml",
            401,
        )

    self._hostname = config.hostname
    self._api_key = config.api_key
    self._ssl_verify = config.ssl_verify
    self._redirect = config.redirect
    self._version = ver
    self._logger = logger or logging.getLogger(__name__)

    self._connect(config.hostname)
```

- [ ] **Step 4: Fix existing test fixture — `MyDepositApi` passes empty api_key**

In `tests/tests/test_deposit_api.py`, the `MyDepositApi.__init__` currently defaults `api_key=""` which will now raise. Update the `setUp` call to pass a dummy key:

```python
class MyDepositApi(DepositApi):
    """Wrapper class to provide access to internal rest_adapter"""

    def __init__(
        self,
        hostname: str = "https://example.com",
        api_key: str = "test-api-key",  # changed: non-empty dummy key
        ver: str = "v1",
        ssl_verify: bool = True,
        logger: logging.Logger = None,
    ):
        super(MyDepositApi, self).__init__(hostname, api_key, ver, ssl_verify, redirect=False, logger=logger)
        self.rest_adapter = self._rest_adapter
```

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS. Pay particular attention that existing `DepositApiTests` still pass with the updated fixture.

- [ ] **Step 6: Commit**

```bash
git add src/nextdep_dsp/deposition/deposit_api.py tests/tests/test_deposit_api.py tests/test_config.py
git commit -m "feat: wire DepositConfig into DepositApi with fail-fast api_key guard"
```

---

## Task 6: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG/v0.1.0.md`

- [ ] **Step 1: Add breaking change entry**

`CHANGELOG/v0.1.0.md` currently contains only "First release on PyPI." Append the following after that line:

```markdown
## Config layer

Added layered configuration support. `api_key`, `hostname`, `ssl_verify`, and `redirect`
can now be set via `~/.config/nextdep/config.toml` or environment variables
(`ONEDEP_API_KEY`, `ONEDEP_HOSTNAME`, `ONEDEP_SSL_VERIFY`, `ONEDEP_REDIRECT`).
Constructor arguments still take highest priority.

**Breaking changes:**
- `DepositApi()` now raises `DepositApiException(401)` immediately at instantiation
  if no `api_key` is configured anywhere (file, env var, or constructor arg).
  Previously, an empty `api_key` would proceed silently and fail at the first HTTP call.
- Callers that relied on `api_key=""` as the default (either explicitly or by omission)
  must now supply a real key or configure one via the config file or env var.
```

- [ ] **Step 2: Run final test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG/v0.1.0.md
git commit -m "docs: document config layer and breaking changes in CHANGELOG"
```

---

## Done

All tasks complete. Verify with:

```bash
pytest tests/ -v --cov=nextdep_dsp --cov-report=term-missing
```

Coverage should meet or exceed the 50% threshold configured in `pyproject.toml`.
