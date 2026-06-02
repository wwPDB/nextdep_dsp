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
    (config_dir / "config.toml").write_text('[default]\napi_key = "mykey"\nunknown_key = "ignored"\n')
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
    (config_dir / "config.toml").write_text('[default]\napi_key = "file-key"\nhostname = "https://file.example.com"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    api = DepositApi()
    assert api._api_key == "file-key"
    assert api._hostname == "https://file.example.com"

from nextdep_dsp.exceptions import ConfigError


def test_defaults_include_schema_and_session_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = DepositConfig()
    assert cfg.api_key is None
    assert cfg.hostname == "https://deposit.wwpdb.org/deposition"
    assert cfg.ssl_verify is True
    assert cfg.redirect is True
    assert cfg.schema_base_url == "https://schemas.wwpdb.org/nextdep"
    assert "schemas" in str(cfg.schema_cache_dir)
    assert "sessions" in str(cfg.session_dir)


def test_constructor_overrides(monkeypatch):
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    cfg = DepositConfig.load(api_key="test-key", ssl_verify=False)
    assert cfg.api_key == "test-key"
    assert cfg.ssl_verify is False


def test_env_var_overrides(monkeypatch):
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "false")
    cfg = DepositConfig.load()
    assert cfg.api_key == "env-key"
    assert cfg.ssl_verify is False


def test_constructor_beats_env_var(monkeypatch):
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    cfg = DepositConfig.load(api_key="override-key")
    assert cfg.api_key == "override-key"


def test_invalid_bool_env_var_raises_config_error(monkeypatch):
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "yes")
    with pytest.raises(ConfigError):
        DepositConfig.load()


def test_schema_base_url_env_override(monkeypatch):
    monkeypatch.setenv("ONEDEP_SCHEMA_URL", "http://localhost:8080/schemas")
    cfg = DepositConfig.load()
    assert cfg.schema_base_url == "http://localhost:8080/schemas"


def test_default_config_path_is_nextdep_toml(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = DepositConfig()
    expected = tmp_path / ".config" / "nextdep" / "config.toml"
    assert cfg.config_path == expected


def test_load_config_path_override_reads_from_given_file(tmp_path):
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text('[default]\napi_key = "custom-key"\n')
    cfg = DepositConfig.load(config_path=cfg_file)
    assert cfg.api_key == "custom-key"
    assert cfg.config_path == cfg_file


def test_read_auth_entry_returns_none_when_key_absent(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[default]\nhostname = "https://example.com"\n')
    cfg = DepositConfig(config_path=cfg_file)
    assert cfg.read_auth_entry("example_com") is None


def test_read_auth_entry_returns_dict_when_present(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[default]\n[auths.example_com]\naccess_token = "tok"\nrefresh_token = "ref"\n'
    )
    cfg = DepositConfig(config_path=cfg_file)
    assert cfg.read_auth_entry("example_com") == {"access_token": "tok", "refresh_token": "ref"}


def test_write_auth_entry_creates_entry_and_preserves_default(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[default]\nhostname = "https://example.com"\n')
    cfg = DepositConfig(config_path=cfg_file)
    cfg.write_auth_entry("example_com", {"access_token": "a", "refresh_token": "r"})
    text = cfg_file.read_text()
    assert "[auths.example_com]" in text
    assert 'access_token = "a"' in text
    assert "[default]" in text


def test_write_auth_entry_updates_existing_entry(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[default]\n[auths.example_com]\naccess_token = "old"\nrefresh_token = "old_r"\n'
    )
    cfg = DepositConfig(config_path=cfg_file)
    cfg.write_auth_entry("example_com", {"access_token": "new", "refresh_token": "new_r"})
    assert cfg.read_auth_entry("example_com") == {"access_token": "new", "refresh_token": "new_r"}


def test_delete_auth_entry_removes_entry_and_preserves_rest(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[default]\nhostname = "https://example.com"\n'
        '[auths.example_com]\naccess_token = "a"\nrefresh_token = "r"\n'
    )
    cfg = DepositConfig(config_path=cfg_file)
    cfg.delete_auth_entry("example_com")
    assert cfg.read_auth_entry("example_com") is None
    assert "[default]" in cfg_file.read_text()


def test_delete_auth_entry_is_noop_when_key_absent(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[default]\nhostname = "https://example.com"\n')
    original = cfg_file.read_text()
    cfg = DepositConfig(config_path=cfg_file)
    cfg.delete_auth_entry("nonexistent")
    assert cfg_file.read_text() == original


def test_write_auth_entry_creates_file_and_parent_dirs_if_missing(tmp_path):
    cfg_file = tmp_path / "subdir" / "config.toml"
    cfg = DepositConfig(config_path=cfg_file)
    cfg.write_auth_entry("example_com", {"access_token": "a", "refresh_token": "r"})
    assert cfg_file.exists()
    assert cfg.read_auth_entry("example_com") == {"access_token": "a", "refresh_token": "r"}
