import os

def get_api_key():
    """Get API key from the file system or environment variable"""
    if os.path.isfile(os.path.expanduser("~/onedepapi.jwt")):
        with open(os.path.expanduser("~/onedepapi.jwt"), "r", encoding="utf-8") as f:
            api_key = f.read().strip()
    else:
        api_key = os.environ.get("ONEDEP_API_KEY")
    if not api_key:
        raise ValueError("API key not found. Please set the ONEDEP_API_KEY environment variable or create a "
                                 "file named onedepapi.jwt in your home directory with the API key.")
    return api_key

def set_api_key(api_key: str):
    """Set API key in the file system or environment variable"""
    try:
        with open(os.path.expanduser("~/onedepapi.jwt"), "w", encoding="utf-8") as f:
            f.write(api_key)
    except Exception as e:
        try:
            os.environ["ONEDEP_API_KEY"] = api_key
        except Exception as env_e:
            raise ValueError(f"Failed to set API key in file system or environment: {e} - {env_e}")
