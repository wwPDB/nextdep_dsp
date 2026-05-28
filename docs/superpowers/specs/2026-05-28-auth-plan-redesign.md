# Auth Plan Redesign

Date: 2026-05-28

## Goal

Revise `docs/superpowers/plans/2026-05-20-auth.md` so Plan 2 implements only reusable token lifecycle management for manually supplied OneDep API credentials. The DSP library will not implement browser/OIDC login in this plan. A package using this library will collect the access token and refresh token from the user through its own UI and pass them to the DSP library.

Also update `docs/superpowers/plans/2026-05-20-api-client.md` so Plan 3 integrates API clients with the revised authentication mechanism.

## Source Authentication Model

The server authentication behavior is documented in `/home/wbueno/repos/onedep/py-wwpdb_apps_deposit/docs/api-authentication.md`.

Relevant behavior:

- Access tokens are JWTs signed with HS256 and last 30 minutes.
- Refresh tokens are opaque strings and last 30 days.
- Tokens are generated manually by a logged-in user in the web UI.
- API requests use `Authorization: Bearer <access_token>`.
- Refresh endpoint: `POST /deposition/auth/tokens/refresh` with JSON body `{"refresh_token": "..."}`.
- Refresh response returns both `access_token` and `refresh_token`.
- Refresh token rotation is mandatory: each refresh invalidates the previous refresh token, so the new refresh token must be persisted immediately.
- Revoke endpoint: `POST /deposition/auth/tokens/revoke` with bearer access token and JSON body `{"refresh_token": "..."}`.
- A `204 No Content` response means revocation succeeded.
- A `401` from refresh means the refresh token is expired, revoked, or invalid; the user must generate and paste a new token pair.

## Architecture Decision

Use a top-level `src/nextdep_dsp/auths/` package for shared authentication code. Do not place authentication modules inside each future API package by default.

Rationale:

- Token persistence, JWT expiry checks, refresh token rotation, and revocation are cross-cutting concerns.
- Duplicating this logic in future packages such as `deposition_api/` and `sequence_api/` would make token lifecycle behavior inconsistent.
- API-specific clients should depend on an auth abstraction. If a future API needs a different auth method, that API can provide a small adapter while still reusing shared auth primitives where possible.

## Plan 2 Scope

Plan 2 should create reusable auth primitives only:

- `src/nextdep_dsp/auths/__init__.py`
- `src/nextdep_dsp/auths/types.py`
- `src/nextdep_dsp/auths/token.py`

Plan 2 should remove all `OidcAuth` implementation and tests from the plan.

Plan 2 should keep deletion of the old `src/nextdep_dsp/authorization/` package, but only after replacement token lifecycle tests pass and no imports remain.

## AuthProvider Shape

The protocol should describe token lifecycle behavior, not browser login:

- `store_tokens(access_token: str, refresh_token: str) -> None`
- `get_access_token() -> str`, returning a valid JWT and refreshing when needed
- `refresh() -> str`, refreshing explicitly and persisting rotated tokens
- `revoke() -> None`, revoking the refresh token and clearing local storage after successful revocation
- `clear_tokens() -> None`, clearing local storage without contacting the server

`login()` should not be part of this protocol for Plan 2.

## Token Storage

Tokens must be stored in the TOML configuration file, not in a separate JSON token file. The auth provider/token manager should use configuration to determine which TOML file to read and write. By default this is the existing `~/.config/nextdep/config.toml`, and Plan 2 must make the config path injectable for tests and embedding applications.

Store token entries under `auths.<normalized-hostname>` TOML tables so multiple remote APIs can coexist. Each entry should contain at least:

```toml
[auths.deposit_wwpdb_org_deposition]
access_token = "eyJ..."
refresh_token = "opaque-string"
```

The plan must require per-host isolation and must not overwrite unrelated `[default]` configuration keys.

Writes must preserve the TOML configuration file as much as practical and use an atomic write pattern: write a temporary file, then `os.replace`.

Malformed or unreadable token data should not silently authenticate. The plan should require `AuthError` for malformed token storage so users are not left with ambiguous auth behavior.

## Refresh And Revocation

`TokenStore` should be initialized with enough API context to build or receive the refresh and revoke URLs. The plan should use the documented full endpoint paths:

- refresh: `/deposition/auth/tokens/refresh`
- revoke: `/deposition/auth/tokens/revoke`

When composing URLs from `DepositConfig.hostname`, avoid accidentally dropping or duplicating `/deposition`. For the current default hostname `https://deposit.wwpdb.org/deposition`, the refresh URL is `https://deposit.wwpdb.org/deposition/auth/tokens/refresh`.

If Plan 3 changes URL composition for API clients, it must keep these auth endpoint paths aligned with the server documentation.

Refresh behavior:

- If the access token is valid, return it.
- If the access token is expired or about to expire, call refresh.
- Persist both returned tokens before returning the new access token.
- If refresh fails with `401`, raise `AuthError` explaining that the user must generate and paste a new token pair.
- If refresh fails for network or malformed response reasons, raise `AuthError` with context.

Revocation behavior:

- Obtain or use a valid access token for the bearer header.
- POST the current refresh token to the revoke endpoint.
- On `204`, remove the local token entry.
- On auth failure, raise `AuthError`; do not silently clear tokens unless the plan explicitly tests that behavior.

## Plan 3 Updates

Update `docs/superpowers/plans/2026-05-20-api-client.md` so API client integration is aware of the changed auth mechanism:

- Replace imports from `nextdep_dsp.auth.*` with `nextdep_dsp.auths.*`.
- Remove `OidcAuth` from public exports and test expectations.
- Make `HttpApiClient` depend on the `AuthProvider`/token manager from Plan 2.
- Before each API request, ask the auth provider for a valid access token and set `Authorization: Bearer <token>`.
- Do not use the stale `/api/v1/auth/token` refresh URL from the old plan. Use the documented full `/deposition/auth/tokens/refresh` endpoint through the auth provider.
- Keep API-client integration in Plan 3, not Plan 2.
- Static `config.api_key` fallback can remain only if the plan explicitly labels it as legacy compatibility during migration.

## Testing Requirements

Plan 2 tests should cover:

- Manual token pair storage in the configured TOML config file.
- Per-hostname isolation.
- JWT expiry detection without signature verification.
- Returning an unexpired access token without network calls.
- Refreshing an expired access token.
- Persisting rotated refresh tokens immediately.
- Raising `AuthError` when refresh token is missing, expired, revoked, invalid, or refresh returns `401`.
- Revoking tokens and clearing local storage on `204`.
- Atomic TOML config writes, preservation of unrelated config keys, and malformed token-data handling.

Plan 3 tests should cover:

- `HttpApiClient` requesting a token from the auth provider before API calls.
- Auth provider refresh behavior being used indirectly when the token manager reports an expired token.
- Public exports matching `auths/` and excluding `OidcAuth`.

## Out Of Scope

- Browser/OIDC login flow.
- UI for collecting tokens from users.
- API-client integration implementation in Plan 2.
- Designing separate auth modules inside each future API package.
