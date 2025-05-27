import settings
import yaml
import os

_config: dict = None


def get_config() -> dict:
    """This is to keep logic of accessing config in one place"""
    global _config
    
    if not settings.CONSERVER_CONFIG_FILE:
        # Return default config for testing
        return {"storages": {"file": {"module": "server.storage.file"}}}
    
    try:
        with open(settings.CONSERVER_CONFIG_FILE) as file:
            _config = yaml.safe_load(file)
            return _config
    except FileNotFoundError:
        # Return default config for testing
        return {"storages": {"file": {"module": "server.storage.file"}}}

class Configuration:
    @classmethod
    def get_config(cls) -> dict:
        return get_config()

    @classmethod
    def get_storages(cls) -> dict:
        config = cls.get_config()
        return config.get("storages", [])  # Changed to [] as default for list

    @classmethod
    def get_followers(cls) -> dict:
        config = cls.get_config()
        return config.get("followers", {})

    @classmethod
    def get_imports(cls) -> dict:
        config = cls.get_config()
        return config.get("imports", {})