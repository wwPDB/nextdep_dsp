import datetime
import os
import re
from pathlib import Path

import jwt
from tomlkit import TOMLDocument

from nextdep_dsp.authorization.token import get_api_key, load_token_config, set_api_key

TEST_CONFIG = str(Path(__file__).with_name("test.toml"))
alg = load_token_config(TEST_CONFIG).get("token").get("alg")
TEST_TOKEN = jwt.encode(
    {"exp": datetime.datetime.now() + datetime.timedelta(days=30)},
    "secret",
    algorithm=alg,
)


def test_config_structure():
    config = load_token_config(TEST_CONFIG)

    assert isinstance(config, TOMLDocument)
    assert "token" in config
    assert "validation" in config

    assert config.get("token").get("file_path") is not None
    assert config.get("token").get("env_var_name") is not None
    assert config.get("token").get("prefer_file") is not None

    assert config.get("validation").get("min_length") is not None
    assert config.get("validation").get("regex") is not None


def test_regex_validation():
    config = load_token_config(TEST_CONFIG)

    pattern = config.get("validation").get("regex")
    assert re.match(pattern, TEST_TOKEN), "Pattern does not match"
    assert not re.match(pattern, "1234567890"), "Pattern matching broken"


def test_min_length_validation():
    config = load_token_config(TEST_CONFIG)
    min_length = int(config.get("validation").get("min_length"))
    assert len(TEST_TOKEN) >= min_length, "Token does not meet minimum length requirement"
    assert 0 < min_length, "Min length validation broken"


def test_get_api_key():
    assert set_api_key(TEST_TOKEN, TEST_CONFIG), "Token not set correctly"
    assert get_api_key(TEST_CONFIG) == TEST_TOKEN, "Token not returned correctly"
    config = load_token_config(TEST_CONFIG)
    filepath = os.path.expanduser(config.get("token").get("file_path"))
    if os.path.exists(filepath):
        os.unlink(filepath)
