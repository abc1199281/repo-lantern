"""Configuration models using Pydantic."""

from typing import Literal

from pydantic import BaseModel, Field


class FilterConfig(BaseModel):
    """File filtering configuration."""

    exclude: list[str] = Field(
        default_factory=list,
        description="Patterns to exclude from analysis",
    )
    include: list[str] = Field(
        default_factory=list,
        description="Patterns to include (overrides exclude)",
    )


class BackendConfig(BaseModel):
    """Backend configuration for LLM."""

    type: Literal["cli", "api"] = Field(
        default="cli",
        description="Backend type: cli or api",
    )

    # CLI backend options
    cli_command: str | None = Field(
        default=None,
        description="CLI command to use (e.g., 'gemini', 'claude')",
    )
    cli_timeout: int = Field(
        default=300,
        description="CLI timeout in seconds",
    )
    cli_fallback_to_api: bool = Field(
        default=False,
        description="Fallback to API if CLI fails",
    )

    # API backend options
    api_provider: Literal["anthropic", "openai", "google", "gemini"] | None = Field(
        default=None,
        description="API provider",
    )
    api_model: str | None = Field(
        default=None,
        description="Model name",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name for API key",
    )


class LanternConfig(BaseModel):
    """Main Lantern configuration."""

    language: str = Field(
        default="en",
        description="Output language (e.g., 'en', 'zh-TW')",
    )
    output_dir: str = Field(
        default=".lantern",
        description="Output directory for generated documentation",
    )
    filter: FilterConfig = Field(
        default_factory=FilterConfig,
        description="File filtering configuration",
    )
    backend: BackendConfig = Field(
        default_factory=BackendConfig,
        description="Backend configuration",
    )
