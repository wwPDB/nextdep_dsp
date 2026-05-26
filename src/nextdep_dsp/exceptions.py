class NextDepError(Exception):
    """Base exception for all nextdep_dsp errors."""


class AuthError(NextDepError):
    """OIDC flow failure or token expired/invalid."""


class ApiError(NextDepError):
    """HTTP error from the OneDep API."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigError(NextDepError, ValueError):
    """Missing or invalid configuration."""


class SchemaError(NextDepError):
    """Schema fetch failure, cache corruption, or validation engine error."""


DepositApiException = ApiError
