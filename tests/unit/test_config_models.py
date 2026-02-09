"""Tests for configuration models."""

import pytest
from pydantic import ValidationError

from lantern_cli.config.models import (
    BackendConfig,
    FilterConfig,
    LanternConfig,
)


class TestFilterConfig:
    """Test FilterConfig model."""

    def test_default_values(self) -> None:
        """Test default filter configuration."""
        config = FilterConfig()
        assert config.exclude == []
        assert config.include == []

    def test_exclude_patterns(self) -> None:
        """Test exclude patterns."""
        config = FilterConfig(exclude=["tests/", "*.generated.*"])
        assert "tests/" in config.exclude
        assert "*.generated.*" in config.exclude

    def test_include_patterns(self) -> None:
        """Test include patterns override exclude."""
        config = FilterConfig(
            exclude=["tests/"],
            include=["tests/integration/"],
        )
        assert "tests/" in config.exclude
        assert "tests/integration/" in config.include


class TestBackendConfig:
    """Test BackendConfig model."""

    def test_default_backend_type(self) -> None:
        """Test default backend type is CLI."""
        config = BackendConfig()
        assert config.type == "cli"

    def test_cli_backend_config(self) -> None:
        """Test CLI backend configuration."""
        config = BackendConfig(
            type="cli",
            cli_command="gemini",
            cli_timeout=300,
        )
        assert config.type == "cli"
        assert config.cli_command == "gemini"
        assert config.cli_timeout == 300

    def test_api_backend_config(self) -> None:
        """Test API backend configuration."""
        config = BackendConfig(
            type="api",
            api_provider="anthropic",
            api_model="claude-sonnet-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
        )
        assert config.type == "api"
        assert config.api_provider == "anthropic"
        assert config.api_model == "claude-sonnet-4-20250514"
        assert config.api_key_env == "ANTHROPIC_API_KEY"

    def test_invalid_backend_type(self) -> None:
        """Test invalid backend type raises error."""
        with pytest.raises(ValidationError):
            BackendConfig(type="invalid")  # type: ignore[arg-type]


class TestLanternConfig:
    """Test LanternConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = LanternConfig()
        assert config.language == "en"
        assert config.output_dir == ".lantern"
        assert isinstance(config.filter, FilterConfig)
        assert isinstance(config.backend, BackendConfig)

    def test_custom_language(self) -> None:
        """Test custom language setting."""
        config = LanternConfig(language="zh-TW")
        assert config.language == "zh-TW"

    def test_custom_output_dir(self) -> None:
        """Test custom output directory."""
        config = LanternConfig(output_dir="/custom/output")
        assert config.output_dir == "/custom/output"

    def test_nested_filter_config(self) -> None:
        """Test nested filter configuration."""
        config = LanternConfig(
            filter=FilterConfig(
                exclude=["tests/", "docs/"],
                include=["tests/integration/"],
            )
        )
        assert "tests/" in config.filter.exclude
        assert "tests/integration/" in config.filter.include

    def test_nested_backend_config(self) -> None:
        """Test nested backend configuration."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="openai",
                api_model="gpt-4",
            )
        )
        assert config.backend.type == "api"
        assert config.backend.api_provider == "openai"
