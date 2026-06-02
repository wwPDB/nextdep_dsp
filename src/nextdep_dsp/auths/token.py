from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import jwt as pyjwt
import requests
import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from nextdep_dsp.config import DepositConfig
from nextdep_dsp.exceptions import AuthError

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "nextdep" / "config.toml"
_REFRESH_PATH = "auth/tokens/refresh"
_REVOKE_PATH = "auth/tokens/revoke"


class TokenStore:
    def __init__(self, config: DepositConfig, config_path: Path | None = None) -> None:
        self._config = config
        self._config_path = config_path or _DEFAULT_CONFIG_PATH

    def store_tokens(self, access_token: str, refresh_token: str) -> None:
        data = self._read_config()
        auths = data.setdefault("auths", {})
        if not isinstance(auths, dict):
            raise AuthError("Malformed token data in config.toml")
        auths[self._fqdn_key()] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
        self._write_config(data)

    def get_access_token(self) -> str:
        entry = self._read_entry()
        token = entry["access_token"]
        if self._is_expired(token):
            return self.refresh()
        return token

    def refresh(self) -> str:
        entry = self._read_entry()
        try:
            response = requests.post(
                self._url(_REFRESH_PATH),
                json={"refresh_token": entry["refresh_token"]},
                verify=self._config.ssl_verify,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise AuthError(f"Token refresh failed: {exc}") from exc

        if response.status_code == 401:
            raise AuthError(
                "Refresh token is expired, revoked, or invalid; generate and paste a new token pair."
            )

        try:
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            raise AuthError(f"Token refresh failed: {exc}") from exc

        access_token = body.get("access_token")
        refresh_token = body.get("refresh_token")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise AuthError(
                "Token refresh response missing access_token or refresh_token"
            )

        self.store_tokens(access_token, refresh_token)
        return access_token

    def revoke(self) -> None:
        entry = self._read_entry()
        access_token = self.get_access_token()
        try:
            response = requests.post(
                self._url(_REVOKE_PATH),
                headers={"Authorization": f"Bearer {access_token}"},
                json={"refresh_token": entry["refresh_token"]},
                verify=self._config.ssl_verify,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise AuthError(f"Token revoke failed: {exc}") from exc

        if response.status_code != 204:
            raise AuthError(f"Token revoke failed with status {response.status_code}")
        self.clear_tokens()

    def clear_tokens(self) -> None:
        data = self._read_config()
        auths = data.setdefault("auths", {})
        if not isinstance(auths, dict):
            raise AuthError("Malformed token data in config.toml")
        auths.pop(self._fqdn_key(), None)
        self._write_config(data)

    def _read_entry(self) -> dict[str, str]:
        data = self._read_config()
        auths = data.get("auths", {})
        if not isinstance(auths, dict):
            raise AuthError("Malformed token data in config.toml")
        entry = auths.get(self._fqdn_key())
        if not entry:
            raise AuthError("No access token stored. Paste a token pair first.")
        if not isinstance(entry, dict):
            raise AuthError("Malformed token data in config.toml")
        access_token = entry.get("access_token")
        refresh_token = entry.get("refresh_token")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise AuthError("Malformed token data in config.toml")
        return {"access_token": access_token, "refresh_token": refresh_token}

    def _read_config(self) -> dict:
        if not self._config_path.exists():
            return {}
        try:
            with self._config_path.open("rb") as fp:
                raw = tomllib.load(fp)
        except tomllib.TOMLDecodeError as exc:
            raise AuthError(f"Failed to parse token config: {exc}") from exc
        if not isinstance(raw, dict):
            raise AuthError("Malformed token data in config.toml")
        return raw

    def _write_config(self, data: dict) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._config_path.with_suffix(".toml.tmp")
        try:
            tmp.write_text(tomli_w.dumps(data))
            os.replace(tmp, self._config_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _fqdn_key(self) -> str:
        parsed = urlparse(self._config.hostname)
        hostname = parsed.hostname
        if hostname is None:
            hostname = urlparse(f"https://{self._config.hostname}").hostname
        if not hostname:
            raise AuthError(f"Invalid hostname for token storage: {self._config.hostname!r}")
        return hostname.replace(".", "_").replace("-", "_")

    def _url(self, path: str) -> str:
        base = self._config.hostname.rstrip("/") + "/"
        return urljoin(base, path)

    def _is_expired(self, token: str) -> bool:
        try:
            payload = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["HS256", "RS256", "none"],
            )
            exp = payload.get("exp")
            return not isinstance(exp, int) or exp < time.time() + 60
        except Exception:
            return True
