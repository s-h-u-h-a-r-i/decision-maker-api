import os
import logging
from enum import StrEnum, auto
from typing import Generic, TypeVar, Optional, Callable, cast
from functools import lru_cache, _CacheInfo

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Key(StrEnum):
    MODE = auto()
    HOST = auto()
    PORT = auto()
    GCP_PROJECT_ID = auto()
    GCP_RESOURCE_TYPE = auto()


class Mode(StrEnum):
    DEVELOPMENT = auto()
    PRODUCTION = auto()


class ModeConditionalDefault(Generic[T]):
    """Represents a default value that should only be applied in specific modes."""

    value: T
    allowed_modes: set[Mode]

    def __init__(self, value: T, allowed_modes: set[Mode] | Mode):
        self.value = value
        if isinstance(allowed_modes, Mode):
            self.allowed_modes = {allowed_modes}
        else:
            self.allowed_modes = allowed_modes

    def should_apply(self, current_mode: Mode) -> bool:
        """Check if this default should be applied given the current mode."""
        return current_mode in self.allowed_modes


class EnvironmentVariable(Generic[T]):
    _key: Key
    _default: Optional[T]
    _mode_conditional_default: Optional[ModeConditionalDefault[T]]
    _sensitive: bool
    _validator: Optional[Callable[[str], bool]]
    _converter: Callable[[str], T]

    def __init__(
        self,
        key: Key,
        *,
        sensitive: bool,
        default: Optional[T] = None,
        mode_conditional_default: Optional[ModeConditionalDefault[T]] = None,
        validator: Optional[Callable[[str], bool]] = None,
        converter: Callable[[str], T] = lambda x: cast(T, x),
    ) -> None:
        self._key = key
        self._default = default
        self._mode_conditional_default = mode_conditional_default
        self._sensitive = sensitive
        self._validator = validator
        self._converter = converter

    def get_validated_value(self, current_mode: Optional[Mode] = None) -> T:
        """
        ### Retrieves and validates the value of an environment variable based on the current mode.

        This method attempts to retrieve the value of the environment variable specified by `_key`.
        If the value is not found, it checks for a default value or a mode conditional default value
        based on the current mode. If the value is found, it validates the value using a provided
        validator function if available. If validation fails, an EnvironmentError is raised.
        Finally, the validated value is converted to the expected type using a provided converter
        function and returned.

        Args:
            `current_mode` (Optional[Mode]): The current mode of the application, used to determine
            which default value to apply if the environment variable is not found.

        Returns:
            `T`: The validated and converted value of the environment variable.

        Raises:
            `EnvironmentError`: If the environment variable is not found and no default value is available,
            or if the validation of the value fails.
        """
        raw_value = os.getenv(self._key)

        if raw_value is None:
            logger.debug(
                f"Environment variable '{self._key}' not found, checking defaults"
            )
            return self._handle_raw_value_none(current_mode)

        if raw_value == "":
            raise EnvironmentError(f"Environment variable '{self._key}' is empty")

        if self._validator is not None and not self._validator(raw_value):
            error_message = f"validation failed for '{self._key}'."
            if not self._sensitive:
                error_message += f" raw_value: {raw_value}"
            raise EnvironmentError(error_message)

        if not self._sensitive:
            logger.debug(f"Loaded '{self._key}' from environment: {raw_value}")
        else:
            logger.debug(f"Loaded sensitive variable '{self._key}' from environment")

        return self._converter(raw_value)

    def _handle_raw_value_none(self, current_mode: Optional[Mode]) -> T:
        """
        ### Handles the case where the raw value of the environment variable is None.

        This method checks for a default value or a mode conditional default value
        based on the current mode. If neither is available, it raises an EnvironmentError.

        Args:
            `current_mode` (Optional[Mode]): The current mode of the application.

        Returns:
            `T`: The default or mode conditional default value if available, otherwise raises an EnvironmentError.
        """
        if self._default is not None:
            return self._default

        if (
            self._mode_conditional_default is not None
            and current_mode is not None
            and self._mode_conditional_default.should_apply(current_mode)
        ):
            return self._mode_conditional_default.value

        mode_context = f" (current_mode: {current_mode})" if current_mode else ""
        raise EnvironmentError(
            f"{self._key} environment variable is required{mode_context}. "
            "No default value is available for this mode."
        )


class Settings:
    _mode: Mode
    _host: str
    _port: int
    _gcp_project_id: str
    _gcp_resource_type: str

    def __init__(self) -> None:
        self._mode = EnvironmentVariable[Mode](
            Key.MODE, sensitive=False, converter=Mode
        ).get_validated_value()

        self._host = EnvironmentVariable[str](
            Key.HOST,
            sensitive=False,
            mode_conditional_default=ModeConditionalDefault(
                "0.0.0.0", Mode.DEVELOPMENT
            ),
        ).get_validated_value(self.mode)

        self._port = EnvironmentVariable[int](
            Key.PORT,
            sensitive=False,
            mode_conditional_default=ModeConditionalDefault(8000, Mode.DEVELOPMENT),
            validator=lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            converter=int,
        ).get_validated_value(self.mode)

        self._gcp_project_id = EnvironmentVariable[str](
            Key.GCP_PROJECT_ID, sensitive=False
        ).get_validated_value()

        self._gcp_resource_type = EnvironmentVariable[str](
            Key.GCP_RESOURCE_TYPE,
            sensitive=False,
            mode_conditional_default=ModeConditionalDefault(
                "cloud_run_revision", Mode.DEVELOPMENT
            ),
        ).get_validated_value(self.mode)

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def gcp_project_id(self) -> str:
        return self._gcp_project_id

    @property
    def gcp_resource_type(self) -> str:
        return self._gcp_resource_type

    @property
    def is_development(self) -> bool:
        return self._mode == Mode.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self._mode == Mode.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> None:
    """
    ### Force reload of all settings from environment variables.

    Call this when you need to ensure latest values,
    such as after environment variables have been updated.
    """
    logger.debug("Reloading settings = clearing cache")
    get_settings.cache_clear()


def is_settings_cached() -> bool:
    """Check if settings are currently cached."""
    return bool(get_settings.cache_info().currsize)


def get_settings_cache_info() -> _CacheInfo:
    """Get cache statistics for debugging."""
    return get_settings.cache_info()


__all__ = [
    "get_settings",
    "reload_settings",
    "is_settings_cached",
    "get_settings_cache_info",
]
