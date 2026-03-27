import pytest

from nextdep_dsp.config import DepositConfig, _parse_bool
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.exceptions import DepositApiException


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


def test_env_var_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load()
    assert config.api_key == "env-key"


def test_env_var_hostname(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_HOSTNAME", "https://env.example.com")
    config = DepositConfig.load()
    assert config.hostname == "https://env.example.com"


def test_env_var_empty_hostname_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_HOSTNAME", "")
    config = DepositConfig.load()
    assert config.hostname == "https://deposit.wwpdb.org/deposition"


def test_env_var_ssl_verify_false(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "key")
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "false")
    config = DepositConfig.load()
    assert config.ssl_verify is False


def test_env_var_ssl_verify_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "FALSE")
    config = DepositConfig.load()
    assert config.ssl_verify is False


def test_env_var_redirect_false(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_REDIRECT", "0")
    config = DepositConfig.load()
    assert config.redirect is False


def test_env_var_invalid_bool_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "yes")
    with pytest.raises(ValueError, match="ONEDEP_SSL_VERIFY"):
        DepositConfig.load()


def test_env_var_overrides_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text('[default]\napi_key = "file-key"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load()
    assert config.api_key == "env-key"


def test_constructor_overrides_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    config = DepositConfig.load(api_key="explicit-key")
    assert config.api_key == "explicit-key"


def test_deposit_api_raises_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com")


def test_deposit_api_raises_with_empty_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com", api_key="")


def test_deposit_api_raises_with_empty_env_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ONEDEP_API_KEY", "")
    with pytest.raises(DepositApiException, match="No API key configured"):
        DepositApi(hostname="https://example.com")


def test_deposit_api_ssl_verify_false_not_filtered(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    api = DepositApi(hostname="https://example.com", api_key="key", ssl_verify=False)
    assert api._ssl_verify is False


def test_deposit_api_uses_config_file(monkeypatch, tmp_path):
    config_dir = tmp_path / ".config" / "nextdep"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        '[default]\napi_key = "file-key"\nhostname = "https://file.example.com"\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    api = DepositApi()
    assert api._api_key == "file-key"
    assert api._hostname == "https://file.example.com"
