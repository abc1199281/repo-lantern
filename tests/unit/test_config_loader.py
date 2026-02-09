"""Tests for configuration loading."""

from pathlib import Path

import pytest

from lantern_cli.config.loader import ConfigLoader
from lantern_cli.config.models import LanternConfig


class TestConfigLoader:
    """Test ConfigLoader."""

    def test_load_default_config(self) -> None:
        """Test loading default configuration."""
        # Ensure we don't read existing .lantern/lantern.toml
        loader = ConfigLoader(user_config_path=Path("/no/user"), project_config_path=Path("/no/proj"))
        config = loader.load()
        assert isinstance(config, LanternConfig)
        assert config.language == "en"
        assert config.output_dir == ".lantern"

    def test_load_from_toml_file(self, tmp_path: Path) -> None:
        """Test loading configuration from TOML file."""
        config_file = tmp_path / "lantern.toml"
        config_file.write_text("""
[lantern]
language = "zh-TW"
output_dir = "/custom/output"

[filter]
exclude = ["tests/", "docs/"]
include = ["tests/integration/"]

[backend]
type = "api"
api_provider = "anthropic"
api_model = "claude-sonnet-4"
""")

        loader = ConfigLoader(project_config_path=config_file)
        config = loader.load()

        assert config.language == "zh-TW"
        assert config.output_dir == "/custom/output"
        assert "tests/" in config.filter.exclude
        assert "tests/integration/" in config.filter.include
        assert config.backend.type == "api"
        assert config.backend.api_provider == "anthropic"

    def test_config_priority_cli_overrides_file(self, tmp_path: Path) -> None:
        """Test CLI arguments override file configuration."""
        config_file = tmp_path / "lantern.toml"
        config_file.write_text("""
[lantern]
language = "zh-TW"
output_dir = "/file/output"
""")

        loader = ConfigLoader(project_config_path=config_file)
        config = loader.load(
            cli_overrides={
                "language": "ja",
                "output_dir": "/cli/output",
            }
        )

        assert config.language == "ja"  # CLI override
        assert config.output_dir == "/cli/output"  # CLI override

    def test_load_nonexistent_file_returns_default(self) -> None:
        """Test loading nonexistent file returns default config."""
        loader = ConfigLoader(project_config_path=Path("/nonexistent/lantern.toml"))
        config = loader.load()
        assert isinstance(config, LanternConfig)
        assert config.language == "en"

    def test_merge_user_and_project_config(self, tmp_path: Path) -> None:
        """Test merging user and project configurations."""
        user_config = tmp_path / "user_lantern.toml"
        user_config.write_text("""
[lantern]
language = "zh-TW"

[backend]
type = "api"
api_provider = "openai"
""")

        project_config = tmp_path / "project_lantern.toml"
        project_config.write_text("""
[lantern]
output_dir = "/project/output"

[filter]
exclude = ["tests/"]
""")

        loader = ConfigLoader(
            user_config_path=user_config,
            project_config_path=project_config,
        )
        config = loader.load()

        # Project config overrides user config
        assert config.output_dir == "/project/output"
        # User config provides defaults
        assert config.language == "zh-TW"
        assert config.backend.api_provider == "openai"
        # Project-specific settings
        assert "tests/" in config.filter.exclude

    def test_invalid_toml_raises_error(self, tmp_path: Path) -> None:
        """Test invalid TOML raises appropriate error."""
        config_file = tmp_path / "lantern.toml"
        config_file.write_text("invalid toml content [[[")

        loader = ConfigLoader(project_config_path=config_file)
        with pytest.raises(Exception):  # Should raise TOMLDecodeError or similar
            loader.load()
