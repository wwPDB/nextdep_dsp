from tomlkit import parse, dumps, TOMLDocument
import os
import re
from pathlib import Path
import jwt
import time
import logging

logger = logging.getLogger(__name__)


def load_token_config(configfile=None) -> TOMLDocument:
    """Load token parser with data from token.toml.

    Args:
        configfile (str): Path to the config file. If None, defaults to "token.toml".

    Returns:
        TOMLDocument: token parser instance
    """
    if configfile is None:
        config_path = Path(__file__).with_name("token.toml")
    else:
        # resolve path in platform-agnostic way
        config_path = Path(configfile).expanduser().resolve()

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = parse(f.read())

    return config_data


def get_api_key(configfile=None) -> str:
    """Get API key from the file system or environment variable.

    Args:
        configfile (str): Path to the config file. If None, defaults to "token.toml".

    Returns:
        str: API key to set.
    """
    config = load_token_config(configfile)

    api_key = None

    if bool(config.get("token").get("prefer_file")) == True:
        file_path = os.path.expanduser(
            config.get("token").get("file_path", "~/.config/nextdep/config.toml")
        )
        if os.path.isfile(file_path):
            with open(
                file_path, "r", encoding=config.get("token").get("encoding")
            ) as f:
                keyfile = parse(f.read())
                api_key = keyfile.get("default").get("api_key")
    else:
        env_var_name = config.get("token").get("env_var_name", "ONEDEP_API_KEY")
        api_key = os.environ.get(env_var_name)

    if not api_key:
        raise ValueError("API key not found.")

    return api_key


def set_api_key(api_key: str, configfile=None) -> bool:
    """Set API key in the file system or environment variable.
    Tomlkit reads and writes toml files in utf-8 encoding and supports python versions from 3.9.

    Args:
        api_key (str): API key to set.

    Raises:
        ValueError: If api key does not pass simple validation.
    """

    if not validate_api_key(api_key, configfile):
        raise ValueError("API key is not valid.")

    config = load_token_config(configfile)

    if bool(config.get("token").get("prefer_file")) == True:
        file_path = os.path.expanduser(
            config.get("token").get("file_path", "~/.config/nextdep/config.toml")
        )
        toml = None
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        if not os.path.isfile(file_path):
            content = f"""[default]
            api_key = "{api_key}"
            hostname = "https://onedep-depui-test.wwpdb.org/deposition"
            ssl_verify = false
            redirect = true
            """
            toml = parse(content)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                toml = parse(f.read())
                toml["default"]["api_key"] = api_key
        with open(file_path, "w", encoding=config.get("token").get("encoding")) as f:
            if toml:
                f.write(dumps(toml))
    else:
        env_var_name = config.get("token").get("env_var_name", "ONEDEP_API_KEY")
        os.environ[env_var_name] = api_key

    return True


def validate_api_key(api_key: str, configfile: str) -> bool:
    """Validate API key.

    Args:
        api_key (str): API key to validate.
        configfile (str): Path to the configuration file.

    Returns:
        bool: True if the API key is valid, False otherwise.
    """
    config = load_token_config(configfile)

    if len(api_key) < int(config.get("validation").get("min_length")):
        logger.error("API key does not meet the minimum length requirement.")
        return False

    pattern = config.get("validation").get("regex")
    if not re.match(r"%s" % pattern, api_key):
        logger.error("API key contains invalid characters.")
        return False

    alg = config.get("token").get("alg")
    decoded_token = jwt.decode(
        api_key, algorithms=[alg], options={"verify_signature": False}
    )
    expiration_time = decoded_token.get("exp")
    if expiration_time is None or expiration_time <= int(time.time()):
        return False

    return True
