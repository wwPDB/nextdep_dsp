import configparser
import os
import re
from pathlib import Path


def load_token_config(configfile=None) -> configparser.ConfigParser:
    """Load config parser with data from token.cfg.

    Args:
        configfile (str): Path to the config file. If None, defaults to "token.cfg".

    Returns:
        ConfigParser: token parser instance
    """
    if configfile is None:
        config_path = Path(__file__).with_name("token.cfg")
    else:
        config_path = Path(configfile).expanduser().resolve()

    config = configparser.ConfigParser()
    config.read(config_path)

    return config


def get_api_key(configfile=None) -> str:
    """Get API key from the file system or environment variable."""
    config = load_token_config(configfile)

    api_key = None

    if config.getboolean("token", "prefer_file") == True:
        file_path = os.path.expanduser(
            config.get("token", "file_path", fallback="~/onedepapi.jwt")
        )
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding=config.get("token", "encoding")) as f:
                api_key = f.read().strip()
    else:
        env_var_name = config.get("token", "env_var_name", fallback="ONEDEP_API_KEY")
        api_key = os.environ.get(env_var_name)

    if not api_key:
        raise ValueError("API key not found.")

    return api_key


def set_api_key(api_key: str, configfile=None) -> bool:
    """Set API key in the file system or environment variable.

    Args:
        api_key (str): API key to set.

    Raises:
        ValueError: If api key does not pass validation.
    """

    config = load_token_config(configfile)

    if len(api_key) < config.getint("validation", "min_length"):
        raise ValueError("API key does not meet the minimum length requirement.")

    pattern = config.get("validation", "regex")
    if not re.match(r"%s" % pattern, api_key):
        raise ValueError("API key contains invalid characters.")

    if config.getboolean("token", "prefer_file") == True:
        file_path = os.path.expanduser(
            config.get("token", "file_path", fallback="~/onedepapi.jwt")
        )
        with open(file_path, "w", encoding=config.get("token", "encoding")) as f:
            f.write(api_key)
    else:
        env_var_name = config.get("token", "env_var_name", fallback="ONEDEP_API_KEY")
        os.environ[env_var_name] = api_key

    return True
