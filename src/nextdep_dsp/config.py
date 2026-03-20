from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


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
        return cls()  # placeholder — wired up in later tasks
