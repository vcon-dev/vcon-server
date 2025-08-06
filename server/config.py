import settings
import yaml

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
        return config.get("storages", {})

    @classmethod
    def get_followers(cls) -> dict:
        config = cls.get_config()
        return config.get("followers", {})

    @classmethod
    def get_imports(cls) -> dict:
        config = cls.get_config()
        return config.get("imports", {})

    @classmethod
    def get_ingress_auth(cls) -> dict:
        """Get ingress-specific API key configuration.

        Returns:
            dict: Dictionary mapping ingress list names to their API keys.
                  Values can be either a single string (one API key) or
                  a list of strings (multiple API keys for the same ingress list).
        """
        config = cls.get_config()
        return config.get("ingress_auth", {})
