"""Tests for LangSmith observability configuration."""

import os
from unittest.mock import patch

from lantern_cli.config.models import LangSmithConfig
from lantern_cli.utils.observability import configure_langsmith


class TestConfigureLangsmith:
    """Test configure_langsmith function."""

    def test_disabled_returns_false(self) -> None:
        """When enabled=False, tracing should not be configured."""
        config = LangSmithConfig(enabled=False)
        assert configure_langsmith(config) is False

    def test_enabled_without_api_key_returns_false(self) -> None:
        """When enabled but API key env var is not set, returns False."""
        config = LangSmithConfig(enabled=True, api_key_env="LANGCHAIN_API_KEY")
        with patch.dict(os.environ, {}, clear=True):
            assert configure_langsmith(config) is False

    def test_enabled_with_api_key_sets_env_vars(self) -> None:
        """When enabled and API key is available, env vars are set correctly."""
        config = LangSmithConfig(
            enabled=True,
            api_key_env="TEST_LANGSMITH_KEY",
            project="test-project",
            endpoint="https://custom.endpoint.com",
        )
        env = {"TEST_LANGSMITH_KEY": "lsv2_test_key_123"}
        with patch.dict(os.environ, env, clear=True):
            result = configure_langsmith(config)

            assert result is True
            assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
            assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_test_key_123"
            assert os.environ["LANGCHAIN_PROJECT"] == "test-project"
            assert os.environ["LANGCHAIN_ENDPOINT"] == "https://custom.endpoint.com"

    def test_default_config_values(self) -> None:
        """Test default LangSmithConfig values."""
        config = LangSmithConfig()
        assert config.enabled is False
        assert config.api_key_env == "LANGCHAIN_API_KEY"
        assert config.project == "repo-lantern"
        assert config.endpoint == "https://api.smith.langchain.com"


class TestLangSmithConfigInLanternConfig:
    """Test LangSmithConfig integration in LanternConfig."""

    def test_default_langsmith_config(self) -> None:
        """LanternConfig should include a default LangSmithConfig."""
        from lantern_cli.config.models import LanternConfig

        config = LanternConfig()
        assert isinstance(config.langsmith, LangSmithConfig)
        assert config.langsmith.enabled is False

    def test_custom_langsmith_config(self) -> None:
        """LanternConfig should accept custom LangSmithConfig."""
        from lantern_cli.config.models import LanternConfig

        config = LanternConfig(
            langsmith=LangSmithConfig(
                enabled=True,
                project="my-project",
            )
        )
        assert config.langsmith.enabled is True
        assert config.langsmith.project == "my-project"
