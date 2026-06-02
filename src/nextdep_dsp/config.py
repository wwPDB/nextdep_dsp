from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Callable

import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from nextdep_dsp.exceptions import ConfigError


def _parse_bool(value: str, var_name: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ConfigError(f"{var_name}={value!r} is not a valid boolean. Use 'true', 'false', '1', or '0'.")


_ENV_MAP: dict[str, tuple[str, Callable[[str], object]]] = {
    "ONEDEP_API_KEY": ("api_key", str),
    "ONEDEP_HOSTNAME": ("hostname", str),
    "ONEDEP_SSL_VERIFY": ("ssl_verify", lambda v: _parse_bool(v, "ONEDEP_SSL_VERIFY")),
    "ONEDEP_REDIRECT": ("redirect", lambda v: _parse_bool(v, "ONEDEP_REDIRECT")),
    "ONEDEP_SCHEMA_URL": ("schema_base_url", str),
}


@dataclass
class DepositConfig:
    api_key: str | None = None
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True
    schema_base_url: str = "https://schemas.wwpdb.org/nextdep"
    schema_cache_dir: Path = field(default_factory=lambda: Path.home() / ".nextdep" / "schemas")
    session_dir: Path = field(default_factory=lambda: Path.home() / ".nextdep" / "sessions")
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".config" / "nextdep" / "config.toml"
    )

    @classmethod
    def load(cls, **overrides: object) -> DepositConfig:
        valid_fields = {f.name for f in fields(cls)}
        merged: dict[str, object] = {}

        config_path_override = overrides.pop("config_path", None)
        config_file = (
            Path(config_path_override)  # type: ignore[arg-type]
            if config_path_override is not None
            else Path.home() / ".config" / "nextdep" / "config.toml"
        )
        merged["config_path"] = config_file

        if config_file.exists():
            try:
                with open(config_file, "rb") as fp:
                    raw = tomllib.load(fp)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(f"Failed to parse {config_file}: {exc}") from exc
            section = raw.get("default", {})
            for key, value in section.items():
                if key in valid_fields and key != "config_path":
                    if key == "hostname" and value == "":
                        continue
                    merged[key] = value

        for env_var, (field_name, coerce) in _ENV_MAP.items():
            raw_val = os.environ.get(env_var)
            if raw_val is not None:
                value = coerce(raw_val)
                if field_name == "hostname" and value == "":
                    continue
                merged[field_name] = value

        for key, value in overrides.items():
            if key in valid_fields:
                merged[key] = value

        return cls(**merged)  # type: ignore[arg-type]

    def _read_toml(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            with self.config_path.open("rb") as fp:
                return tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Failed to parse {self.config_path}: {exc}") from exc

    def _write_toml(self, data: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".toml.tmp")
        try:
            tmp.write_text(tomli_w.dumps(data), encoding="utf-8")
            os.replace(tmp, self.config_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def read_auth_entry(self, key: str) -> dict | None:
        data = self._read_toml()
        auths = data.get("auths", {})
        if not isinstance(auths, dict):
            raise ConfigError("Malformed [auths] section in config.toml")
        entry = auths.get(key)
        return entry if isinstance(entry, dict) else None

    def write_auth_entry(self, key: str, entry: dict) -> None:
        data = self._read_toml()
        auths = data.setdefault("auths", {})
        if not isinstance(auths, dict):
            raise ConfigError("Malformed [auths] section in config.toml")
        auths[key] = entry
        self._write_toml(data)

    def delete_auth_entry(self, key: str) -> None:
        data = self._read_toml()
        auths = data.get("auths")
        if not isinstance(auths, dict) or key not in auths:
            return
        del auths[key]
        self._write_toml(data)
