from __future__ import annotations

from dataclasses import dataclass

try:
    import tomllib  # noqa: F401
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # noqa: F401


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
        return cls()  # placeholder — wired up in later tasks
