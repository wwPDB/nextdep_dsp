import pytest

from nextdep_dsp.config import DepositConfig, _parse_bool


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


def test_load_defaults_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"
    assert config.ssl_verify is True
    assert config.redirect is True
    assert config.api_key is None


def test_load_reads_toml_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "mykey"\nhostname = "https://example.com"\nssl_verify = false\nredirect = false\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key == "mykey"
    assert config.hostname == "https://example.com"
    assert config.ssl_verify is False
    assert config.redirect is False


def test_load_skips_missing_default_section(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[other]\napi_key = "ignored"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key is None  # [default] absent → skipped


def test_load_malformed_toml_raises(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("this is not : valid toml [[\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="config.toml"):
        DepositConfig.load()


def test_load_ignores_unknown_keys_in_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "mykey"\nunknown_key = "ignored"\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.api_key == "mykey"  # did not raise


def test_load_empty_hostname_in_file_falls_back(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[default]\nhostname = ""\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"
