import os
from typing import Generator, Any, Dict, Union, Optional
from unittest.mock import patch, MagicMock
from functools import _CacheInfo

import pytest

from app.configs.settings import (
    EnvironmentVariable,
    get_settings,
    get_settings_cache_info,
    is_settings_cached,
    Key,
    Mode,
    ModeConditionalDefault,
    reload_settings,
    Settings,
)


class TestModeConditionalDefault:
    """Test the ModeConditionalDefault class."""

    def test_init_with_single_mode(self) -> None:
        """Tets initialization with a single mode."""
        default = ModeConditionalDefault(
            value="test_value", allowed_modes=Mode.DEVELOPMENT
        )
        assert default.value == "test_value"
        assert default.allowed_modes == {Mode.DEVELOPMENT}

    def test_init_with_multiple_modes(self) -> None:
        """Test initialization with multiple modes."""
        modes: set[Mode] = {Mode.DEVELOPMENT, Mode.PRODUCTION}
        default = ModeConditionalDefault(value="test_value", allowed_modes=modes)
        assert default.value == "test_value"
        assert default.allowed_modes == modes

    def test_should_apply_true(self) -> None:
        """Test should_apply returns True for allowed mode."""
        default = ModeConditionalDefault(
            value="test_value", allowed_modes=Mode.DEVELOPMENT
        )
        assert default.should_apply(current_mode=Mode.DEVELOPMENT) is True

    def test_should_apply_false(self) -> None:
        """Test should_apply returns False for disallowed mode."""
        default = ModeConditionalDefault(
            value="test_value", allowed_modes=Mode.DEVELOPMENT
        )
        assert default.should_apply(current_mode=Mode.PRODUCTION) is False

    def test_should_apply_multiple_modes(self) -> None:
        """Tets should_apply with multiple allowed modes."""
        modes: set[Mode] = {Mode.DEVELOPMENT, Mode.PRODUCTION}
        default = ModeConditionalDefault(value="test_value", allowed_modes=modes)
        assert default.should_apply(current_mode=Mode.DEVELOPMENT) is True
        assert default.should_apply(current_mode=Mode.PRODUCTION) is True


class TestEnvironmentVariable:
    """Test the EnvironmentVariable class."""

    @pytest.fixture(autouse=True)
    def setup_method(self) -> Generator[None, Any, None]:
        """Clean up environment variables before each test."""
        # Store original values
        self.original_env: Dict[Key, Union[str, None]] = {}
        for key in Key:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        yield

        # Restore original values
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    def test_get_validated_value_from_environment(self) -> None:
        """Test getting value from environment variable."""
        os.environ[Key.HOST] = "localhost"
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=False)
        assert env_var.get_validated_value() == "localhost"

    def test_get_validated_empty_string_raises_error(self) -> None:
        """Test that empty string raises EnvironmentError."""
        os.environ[Key.HOST] = ""
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=False)

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="Environment variable 'host' is empty",
        ):
            env_var.get_validated_value()

    def test_get_validated_value_with_validator_success(self) -> None:
        """Test validation passes with valid value."""
        os.environ[Key.PORT] = "8080"
        env_var = EnvironmentVariable[int](
            Key.PORT,
            sensitive=False,
            validator=lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            converter=int,
        )
        assert env_var.get_validated_value() == 8080

    def test_get_validated_value_with_validator_failure(self) -> None:
        """Test validation fails with invalid value."""
        os.environ[Key.PORT] = "99999"
        env_var = EnvironmentVariable[int](
            key=Key.PORT,
            sensitive=False,
            validator=lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            converter=int,
        )

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="validation failed for 'port'. raw_value: 99999$",
        ):
            env_var.get_validated_value()

    def test_get_validated_value_with_validator_failure_sensitive(self) -> None:
        """Test validation fails with sensitive variable (no value in error)."""
        os.environ[Key.PORT] = "99999"
        env_var = EnvironmentVariable[int](
            key=Key.PORT,
            sensitive=True,
            validator=lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            converter=int,
        )

        with pytest.raises(
            expected_exception=EnvironmentError, match="validation failed for 'port'.$"
        ):
            env_var.get_validated_value()

    def test_get_validated_value_with_converter(self) -> None:
        """Test value conversion works correctly."""
        os.environ[Key.PORT] = "8080"
        env_var = EnvironmentVariable[int](key=Key.PORT, sensitive=False, converter=int)
        result = env_var.get_validated_value()
        assert result == 8080
        assert isinstance(result, int)

    def test_get_validated_value_with_default(self) -> None:
        """Test fallback to default when env var not set."""
        default_var = "default_host"
        env_var = EnvironmentVariable[str](
            Key.HOST, sensitive=False, default=default_var
        )
        assert env_var.get_validated_value() == default_var

    def test_get_validated_value_with_mode_conditional_default_applies(self) -> None:
        """Test mode conditional default is used when mode matches."""
        mode_default = ModeConditionalDefault("dev_host", Mode.DEVELOPMENT)
        env_var = EnvironmentVariable[str](
            Key.HOST, sensitive=False, mode_conditional_default=mode_default
        )
        assert env_var.get_validated_value(Mode.DEVELOPMENT) == "dev_host"

    def test_get_validated_value_with_mode_conditional_default_doesnt_apply(
        self,
    ) -> None:
        mode_default = ModeConditionalDefault("dev_host", Mode.DEVELOPMENT)
        env_var = EnvironmentVariable[str](
            Key.HOST, sensitive=False, mode_conditional_default=mode_default
        )

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="host environment variable is required \\(current_mode: production\\)",
        ):
            env_var.get_validated_value(Mode.PRODUCTION)

    def test_get_validated_value_no_defaults_raises_error(self) -> None:
        """Test error when no defaults available."""
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=False)

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="host environment variable is required. No default value is available",
        ):
            env_var.get_validated_value()

    def test_get_validated_value_no_defaults_with_mode_raises_error(self) -> None:
        """Test error when no defaults available with mode context."""
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=False)
        with pytest.raises(
            expected_exception=EnvironmentError,
            match="host environment variable is required \\(current_mode: development\\)",
        ):
            env_var.get_validated_value(Mode.DEVELOPMENT)

    def test_default_takes_precedence_over_mode_conditional(self) -> None:
        """Test that regular default takes precedence over mode conditional default."""
        mode_default = ModeConditionalDefault("dev_host", Mode.DEVELOPMENT)
        env_var = EnvironmentVariable[str](
            Key.HOST,
            sensitive=False,
            default="regular_default",
            mode_conditional_default=mode_default,
        )
        assert (
            env_var.get_validated_value(current_mode=Mode.DEVELOPMENT)
            == "regular_default"
        )

    @patch("app.configs.settings.logger")
    def test_logging_for_non_sensitive_variable(self, mock_logger: MagicMock) -> None:
        """Test logging behavior for non-sensitive variables."""
        os.environ[Key.HOST] = "localhost"
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=False)
        env_var.get_validated_value()

        mock_logger.debug.assert_called_with(  # type: ignore [attr-defined]
            "Loaded 'host' from environment: localhost"
        )

    @patch("app.configs.settings.logger")
    def test_logging_for_sensitive_variable(self, mock_logger: MagicMock) -> None:
        """Test logging behaviour for sensitive variables."""
        os.environ[Key.HOST] = "localhost"
        env_var = EnvironmentVariable[str](Key.HOST, sensitive=True)
        env_var.get_validated_value()

        mock_logger.debug.assert_called_with(
            "Loaded sensitive variable 'host' from environment"
        )


class TestSettings:
    """Test the settings class."""

    @pytest.fixture(autouse=True)
    def setup_method(self) -> Generator[None, Any, None]:
        """Clean up environment and cache before each test."""
        self.original_env: Dict[Key, Union[str, None]] = {}
        for key in Key:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        get_settings.cache_clear()

        yield

        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        get_settings.cache_clear()

    def test_settings_initialization_development_mode(self) -> None:
        """Test Settings initialization in development mode."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        settings = Settings()

        assert settings.mode == Mode.DEVELOPMENT
        assert settings.host == "0.0.0.0"  # mode conditional default
        assert settings.port == 8000  # mode conditional default
        assert settings.gcp_project_id == "test-project"
        assert (
            settings.gcp_resource_type == "cloud_run_revision"
        )  # mode conditional default
        assert settings.is_development is True
        assert settings.is_production is False

    def test_settings_initialization_production_mode(self) -> None:
        """Test Settings initialization in production mode."""
        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.HOST] = "prod-host"
        os.environ[Key.PORT] = "9000"
        os.environ[Key.GCP_PROJECT_ID] = "prod-project"
        os.environ[Key.GCP_RESOURCE_TYPE] = "gce_instance"

        settings = Settings()

        assert settings.mode == Mode.PRODUCTION
        assert settings.host == "prod-host"
        assert settings.port == 9000
        assert settings.gcp_project_id == "prod-project"
        assert settings.gcp_resource_type == "gce_instance"
        assert settings.is_development is False
        assert settings.is_production is True

    def test_settings_port_validation_success(self) -> None:
        """Test port validation with valid port."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.PORT] = "8080"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        settings = Settings()
        assert settings.port == 8080

    def test_settings_port_validation_failure_too_high(self) -> None:
        """Test port validation fails with port too high."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.PORT] = "99999"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError, match="validation failed for 'port'"
        ):
            Settings()

    def test_settings_port_validation_failure_zero(self) -> None:
        """Test port validation fails with port zero."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.PORT] = "0"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError, match="validation failed for 'port'"
        ):
            Settings()

    def test_settings_port_validation_failure_non_numeric(self) -> None:
        """Test port validation fails with non-numeric value."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.PORT] = "not-a-number"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError, match="validation failed for 'port'"
        ):
            Settings()

    def test_settings_missing_required_mode(self) -> None:
        """Test Settings fails when MODE is missing"""
        with pytest.raises(
            expected_exception=EnvironmentError,
            match="mode environment variable is required",
        ):
            Settings()

    def test_settings_missing_required_gcp_project_id(self) -> None:
        """Test Settings fails when MODE is missing."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="gcp_project_id environment variable is required",
        ):
            Settings()

    def test_settings_missing_host_in_production(self) -> None:
        """Test Settings fails when HOST is missing in production mode."""
        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="host environment variable is required \\(current_mode: production\\)",
        ):
            Settings()

    def test_settings_missing_port_in_production(self) -> None:
        """Test Settings fails when PORT is missing in production mode."""
        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.HOST] = "prod-host"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="port environment variable is required \\(current_mode: production\\)",
        ):
            Settings()

    def test_settings_missing_gcp_resource_type_in_production(self) -> None:
        """Test Settings fails when GCP_RESOURCE_TYPE is missing in production mode."""
        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.HOST] = "prod-host"
        os.environ[Key.PORT] = "9000"
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        with pytest.raises(
            expected_exception=EnvironmentError,
            match="gcp_resource_type environment variable is required \\(current_mode: production\\)",
        ):
            Settings()


class TestCachingFunctions:
    """Test the module-level caching functions."""

    @pytest.fixture(autouse=True)
    def setup_method(self) -> Generator[None, Any, None]:
        """Clean up environment and cache before each test."""
        self.original_env: Dict[Key, Optional[str]] = {}
        for key in Key:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        # Set required environment variables for valid settings
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.GCP_PROJECT_ID] = "test-project"

        get_settings.cache_clear()

        yield

        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        get_settings.cache_clear()

    def test_get_settins_returns_same_intance(self) -> None:
        """Test that get_settings returns the same cached instance."""
        settings1: Settings = get_settings()
        settings2: Settings = get_settings()

        assert settings1 is settings2

    def test_get_settings_cache_info_initial_state(self) -> None:
        """Test cach info before any calls"""
        cache_info: _CacheInfo = get_settings_cache_info()

        assert isinstance(cache_info, _CacheInfo)
        assert cache_info.currsize == 0
        assert cache_info.maxsize == 1

    def test_get_settings_cache_info_after_call(self) -> None:
        """Test cache info after getting settings."""
        get_settings()
        cache_info: _CacheInfo = get_settings_cache_info()

        assert cache_info.currsize == 1
        assert cache_info.hits == 0
        assert cache_info.misses == 1

    def test_get_settings_cache_info_after_multiple_calls(self) -> None:
        """Test cache info after multiple calls."""
        get_settings()
        get_settings()
        get_settings()
        cache_info: _CacheInfo = get_settings_cache_info()

        assert cache_info.currsize == 1
        assert cache_info.hits == 2
        assert cache_info.misses == 1

    def test_is_settings_cached_false_initiall(self) -> None:
        """Test is_settings_cached returns False initally."""
        assert is_settings_cached() is False

    def test_is_settings_cached_true_after_call(self) -> None:
        """Test is_settings_cached returns True after getting settings."""
        get_settings()
        assert is_settings_cached() is True

    def test_reload_settings_clears_cache(self) -> None:
        """Test that reload_settings clears the cache."""
        get_settings()
        assert is_settings_cached() is True

        reload_settings()
        assert is_settings_cached() is False

    def test_reload_settings_forces_new_instance(self) -> None:
        """Test that reload_settings forces creation of new instance."""
        settings1: Settings = get_settings()
        reload_settings()
        settings2: Settings = get_settings()

        assert settings1 is not settings2

    def test_settings_updates_after_env_change_and_reload(self) -> None:
        """Test that settings reflect environment cvhanges after reload."""
        settings1: Settings = get_settings()
        inital_host: str = settings1.host

        os.environ[Key.HOST] = "new-host"

        # settings should still return old cached value
        settings2: Settings = get_settings()
        assert settings2.host == inital_host

        # settings should reflect new host after reloading
        reload_settings()
        settings3: Settings = get_settings()
        assert settings3.host == "new-host"


class TestIntegration:
    """Integration tests for the complete settings system."""

    @pytest.fixture(autouse=True)
    def setup_method(self) -> Generator[None, Any, None]:
        """Clean up environment and cache before each test."""
        self.original_env: Dict[Key, Optional[str]] = {}
        for key in Key:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        get_settings.cache_clear()

        yield

        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

        get_settings.cache_clear()

    def test_complete_development_configuration(self) -> None:
        """Test complete development environment setup."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.GCP_PROJECT_ID] = "dev-project"

        settings: Settings = get_settings()

        assert settings.mode == Mode.DEVELOPMENT
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.gcp_project_id == "dev-project"
        assert settings.gcp_resource_type == "cloud_run_revision"
        assert settings.is_development is True
        assert settings.is_production is False

        assert is_settings_cached() is True
        cache_info: _CacheInfo = get_settings_cache_info()
        assert cache_info.currsize == 1

    def test_complete_production_configuration(self) -> None:
        """Test complete production environment setup."""
        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.HOST] = "api.example.com"
        os.environ[Key.PORT] = "443"
        os.environ[Key.GCP_PROJECT_ID] = "prod-project-123"
        os.environ[Key.GCP_RESOURCE_TYPE] = "gce_instance"

        settings: Settings = get_settings()

        assert settings.mode == Mode.PRODUCTION
        assert settings.host == "api.example.com"
        assert settings.port == 443
        assert settings.gcp_project_id == "prod-project-123"
        assert settings.gcp_resource_type == "gce_instance"
        assert settings.is_development is False
        assert settings.is_production is True

    def test_mixed_explicit_and_default_values(self) -> None:
        """Test configuration with mix of explicit and default values."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.HOST] = "custom-host"  # Override default
        os.environ[Key.GCP_PROJECT_ID] = "mixed-project"

        settings: Settings = get_settings()

        assert settings.mode == Mode.DEVELOPMENT
        assert settings.host == "custom-host"
        assert settings.port == 8000
        assert settings.gcp_project_id == "mixed-project"
        assert settings.gcp_resource_type == "cloud_run_revision"

    def test_configuration_change_and_reload_workflow(self) -> None:
        """Test realistic workflow of changing configuration and realoding."""
        os.environ[Key.MODE] = Mode.DEVELOPMENT
        os.environ[Key.GCP_PROJECT_ID] = "dev-project"

        settings: Settings = get_settings()
        assert settings.mode == Mode.DEVELOPMENT
        assert settings.port == 8000

        os.environ[Key.MODE] = Mode.PRODUCTION
        os.environ[Key.HOST] = "prod-host"
        os.environ[Key.PORT] = "9000"
        os.environ[Key.GCP_RESOURCE_TYPE] = "gce_instance"

        cached_settigns: Settings = get_settings()
        assert cached_settigns.mode == Mode.DEVELOPMENT

        reload_settings()

        new_settings: Settings = get_settings()
        assert new_settings.mode == Mode.PRODUCTION
        assert new_settings.host == "prod-host"
        assert new_settings.port == 9000
        assert new_settings.gcp_resource_type == "gce_instance"
