from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import jwt as pyjwt
import requests

from nextdep_dsp.config import DepositConfig
from nextdep_dsp.exceptions import AuthError, ConfigError

_REFRESH_PATH = "auth/tokens/refresh"
_REVOKE_PATH = "auth/tokens/revoke"


class TokenStore:
    def __init__(self, config: DepositConfig) -> None:
        self._config = config

    def store_tokens(self, access_token: str, refresh_token: str) -> None:
        try:
            self._config.write_auth_entry(
                self._fqdn_key(),
                {"access_token": access_token, "refresh_token": refresh_token},
            )
        except ConfigError as exc:
            raise AuthError(str(exc)) from exc

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
        try:
            self._config.delete_auth_entry(self._fqdn_key())
        except ConfigError as exc:
            raise AuthError(str(exc)) from exc

    def _read_entry(self) -> dict[str, str]:
        try:
            entry = self._config.read_auth_entry(self._fqdn_key())
        except ConfigError as exc:
            raise AuthError(str(exc)) from exc
        if entry is None:
            raise AuthError("No access token stored. Paste a token pair first.")
        access_token = entry.get("access_token")
        refresh_token = entry.get("refresh_token")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise AuthError("Malformed token data in config.toml")
        return {"access_token": access_token, "refresh_token": refresh_token}

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
