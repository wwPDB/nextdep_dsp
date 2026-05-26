import pytest

from nextdep_dsp.exceptions import (
    ApiError,
    AuthError,
    ConfigError,
    DepositApiException,
    NextDepError,
    SchemaError,
)


def test_all_errors_inherit_from_nextdep_error():
    assert issubclass(AuthError, NextDepError)
    assert issubclass(ApiError, NextDepError)
    assert issubclass(ConfigError, NextDepError)
    assert issubclass(SchemaError, NextDepError)


def test_api_error_stores_status_code():
    err = ApiError("Not found", 404)
    assert err.status_code == 404
    assert str(err) == "Not found"


def test_deposit_api_exception_is_alias_for_api_error():
    assert DepositApiException is ApiError
    err = DepositApiException("Unauthorized", 401)
    assert isinstance(err, NextDepError)


def test_exceptions_are_catchable_as_base():
    with pytest.raises(NextDepError):
        raise AuthError("bad token")
