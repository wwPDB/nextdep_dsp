import os
import configparser
import re
from pathlib import Path
from nextdep_dsp.authorization.token import load_token_config, set_api_key, get_api_key

TEST_CONFIG = str(Path(__file__).with_name("test.cfg"))
TEST_TOKEN = "as5d6ak.asd786f57dsf.a6sd5fa868"


def test_cfg_structure():
    config = load_token_config(TEST_CONFIG)

    assert isinstance(config, configparser.ConfigParser)
    assert config.has_section("token")
    assert config.has_section("validation")

    assert config.has_option("token", "file_path")
    assert config.has_option("token", "env_var_name")
    assert config.has_option("token", "prefer_file")

    assert config.has_option("validation", "min_length")
    assert config.has_option("validation", "regex")


def test_regex_validation():
    config = load_token_config(TEST_CONFIG)

    pattern = config.get("validation", "regex")
    assert re.match(pattern, TEST_TOKEN), "Pattern does not match"
    assert not re.match(pattern, "1234567890"), "Pattern matching broken"


def test_min_length_validation():
    config = load_token_config(TEST_CONFIG)
    min_length = config.getint("validation", "min_length")
    assert (
        len(TEST_TOKEN) >= min_length
    ), "Token does not meet minimum length requirement"
    assert not len("0") >= min_length, "Min length validation broken"


def test_get_api_key():
    config = load_token_config(TEST_CONFIG)
    tokenfile = config.get("token", "file_path")
    if Path(tokenfile).exists():
        Path(tokenfile).unlink()
    assert not os.path.exists(tokenfile), "Token should not exist"
    assert set_api_key(TEST_TOKEN, TEST_CONFIG), "Token not set correctly"
    assert get_api_key(TEST_CONFIG) == TEST_TOKEN, "Token not returned correctly"
