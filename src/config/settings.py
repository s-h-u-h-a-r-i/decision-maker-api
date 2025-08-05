import os
from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""

    pass


class Settings:
    """Centralized application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.google_cloud_project = self._get_required_env("GOOGLE_CLOUD_PROJECT")

        self.is_dev = self._get_env_bool(key="DEV")
        self.log_level = self._get_env(key="LOG_LEVEL", default="INFO")

        self.host = self._get_env(key="HOST", default="0.0.0.0")
        self.port = int(self._get_env(key="PORT", default="8080"))

    def _get_required_env(self, key: str) -> str:
        """Get a required environment variable or raise ConfigError."""
        value = os.getenv(key)
        if value is None:
            raise ConfigError(f"Required environment variable '{key}' is not set")
        return value

    def _get_env(self, *, key: str, default: str) -> str:
        """Get an optional environment variable with a default value."""
        return os.getenv(key, default)

    def _get_env_bool(self, *, key: str, default: bool = False) -> bool:
        """Get a boolean environment variable."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.strip().lower() in {"true", "1", "yes", "on"}


settings = Settings()

__all__ = ["settings"]
