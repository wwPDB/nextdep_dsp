from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


def _parse_bool(value: str, var_name: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ValueError(
        f"{var_name}={value!r} is not a valid boolean. Use 'true', 'false', '1', or '0'."
    )


@dataclass
class DepositConfig:
    api_key: str | None = None
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True

    @classmethod
    def load(cls, **overrides) -> DepositConfig:
        valid_fields = {f.name for f in fields(cls)}
        merged: dict = {}

        # Layer 1: config file
        config_file = Path.home() / ".config" / "nextdep" / "config.toml"
        if config_file.exists():
            try:
                with open(config_file, "rb") as fp:
                    raw = tomllib.load(fp)
            except tomllib.TOMLDecodeError as exc:
                # Only catch parse errors; PermissionError/OSError propagate as-is
                raise ValueError(f"Failed to parse {config_file}: {exc}") from exc
            section = raw.get("default", {})
            for key, value in section.items():
                if key in valid_fields:
                    # Empty-string hostname in file is treated as absent
                    if key == "hostname" and value == "":
                        continue
                    merged[key] = value

        # Layer 2: env vars — added in next task

        # Layer 3: caller overrides (only known fields)
        for key, value in overrides.items():
            if key in valid_fields:
                merged[key] = value

        return cls(**merged)
