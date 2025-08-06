import settings
import yaml
import os

_config: dict = None


def get_config() -> dict:
    """This is to keep logic of accessing config in one place"""
    global _config
    with open(settings.CONSERVER_CONFIG_FILE) as file:
        _config = yaml.safe_load(file)
    return _config


class Configuration:
    @classmethod
    def get_config(cls) -> dict:
        return get_config()

    @classmethod
    def get_storages(cls) -> dict:
        config = cls.get_config()
        all_storages = config.get("storages", {})
        enabled_plugins = os.getenv("STORAGE_PLUGINS", "").split(",")

        # Normalize names (strip whitespace)
        enabled_plugins = [p.strip() for p in enabled_plugins if p.strip()]

        # Only return storages explicitly listed in STORAGE_PLUGINS
        filtered = {
            name: storage
            for name, storage in all_storages.items()
            if name in enabled_plugins
        }

        return filtered

    @classmethod
    def get_followers(cls) -> dict:
        config = cls.get_config()
        return config.get("followers", {})

    @classmethod
    def get_imports(cls) -> dict:
        config = cls.get_config()
        return config.get("imports", {})
    