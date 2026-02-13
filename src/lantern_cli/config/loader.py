"""Configuration loader with TOML parsing and priority system."""

import tomllib
from pathlib import Path
from typing import Any

from lantern_cli.config.models import BackendConfig, FilterConfig, LanternConfig


class ConfigLoader:
    """Load and merge configuration from multiple sources."""

    def __init__(
        self,
        user_config_path: Path | None = None,
        project_config_path: Path | None = None,
    ) -> None:
        """Initialize ConfigLoader.

        Args:
            user_config_path: Path to user config (~/.config/lantern/lantern.toml)
            project_config_path: Path to project config (.lantern/lantern.toml)
        """
        self.user_config_path = (
            user_config_path or Path.home() / ".config" / "lantern" / "lantern.toml"
        )
        self.project_config_path = project_config_path or Path(".lantern") / "lantern.toml"

    def load(self, overrides: dict[str, Any] | None = None) -> LanternConfig:
        """Load configuration with priority: CLI > Project > User > Default.

        Args:
            overrides: structured dictionary of overrides (e.g. from CLI arguments)

        Returns:
            Merged LanternConfig
        """
        # Start with default config
        config_dict: dict[str, Any] = {}

        # Load user config (lowest priority)
        if self.user_config_path.exists():
            user_data = self._load_toml(self.user_config_path)
            config_dict = self._merge_dicts(config_dict, user_data)

        # Load project config (higher priority)
        if self.project_config_path.exists():
            project_data = self._load_toml(self.project_config_path)
            config_dict = self._merge_dicts(config_dict, project_data)

        # Apply overrides (highest priority)
        if overrides:
            config_dict = self._merge_dicts(config_dict, overrides)

        # Extract nested configs
        lantern_config = config_dict.get("lantern", {})
        filter_config = config_dict.get("filter", {})
        backend_config = config_dict.get("backend", {})

        # Build Pydantic models
        return LanternConfig(
            language=lantern_config.get("language", "en"),
            output_dir=lantern_config.get("output_dir", ".lantern"),
            filter=FilterConfig(**filter_config),
            backend=BackendConfig(**backend_config),
        )

    def _load_toml(self, path: Path) -> dict[str, Any]:
        """Load TOML file.

        Args:
            path: Path to TOML file

        Returns:
            Parsed TOML data

        Raises:
            TOMLDecodeError: If TOML is invalid
        """
        with open(path, "rb") as f:
            return tomllib.load(f)

    def _merge_dicts(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result


def _resolve_cli_overrides(
    output: str | None = None,
    lang: str | None = None,
) -> dict[str, Any]:
    """Resolve CLI arguments into configuration overrides dictionary.

    Args:
        output: Output directory override
        lang: Language override

    Returns:
        Dictionary compatible with ConfigLoader.load overrides
    """
    overrides: dict[str, Any] = {"lantern": {}, "backend": {}}
    
    # Basic Lantern Config overrides
    if output is not None:
        overrides["lantern"]["output_dir"] = output
    if lang is not None:
        overrides["lantern"]["language"] = lang
    return overrides


def load_config(
    repo_path: Path,
    output: str | None = None,
    lang: str | None = None,
) -> LanternConfig:
    """Helper to load configuration for a given repository path with CLI overrides.

    Args:
        repo_path: Repository root path.
        output: Output directory override
        lang: Language override

    Returns:
        Loaded LanternConfig.
    """
    loader = ConfigLoader(project_config_path=repo_path / ".lantern" / "lantern.toml")
    
    # 1. Resolve overrides
    overrides = _resolve_cli_overrides(output, lang)
    
    # 2. Load with overrides
    return loader.load(overrides)

