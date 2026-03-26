from tomlkit import parse, dumps, TOMLDocument
import os
import re
from pathlib import Path



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
            config.get("token").get("file_path", "~/onedepapi.jwt")
        )
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding=config.get("token").get("encoding")) as f:
                api_key = f.read().strip()
    else:
        env_var_name = config.get("token").get("env_var_name", "ONEDEP_API_KEY")
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

    if len(api_key) < int(config.get("validation").get("min_length")):
        raise ValueError("API key does not meet the minimum length requirement.")

    pattern = config.get("validation").get("regex")
    if not re.match(r"%s" % pattern, api_key):
        raise ValueError("API key contains invalid characters.")

    if bool(config.get("token").get("prefer_file")) == True:
        file_path = os.path.expanduser(
            config.get("token").get("file_path", "~/onedepapi.jwt")
        )
        with open(file_path, "w", encoding=config.get("token").get("encoding")) as f:
            f.write(api_key)
    else:
        env_var_name = config.get("token").get("env_var_name", "ONEDEP_API_KEY")
        os.environ[env_var_name] = api_key

    return True
