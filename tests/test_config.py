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
