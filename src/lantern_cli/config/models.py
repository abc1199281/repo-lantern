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

    type: Literal["cli", "api", "ollama"] = Field(
        default="cli",
        description="Backend type: cli, api, or ollama",
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
    cli_args_template: list[str] | None = Field(
        default=None,
        description="Template for CLI arguments (e.g., ['{command}', 'exec', '{prompt}'])",
    )

    # API backend options
    api_provider: str | None = Field(
        default=None,
        description="API provider (e.g., 'openai', 'anthropic', 'gemini')",
    )
    api_model: str | None = Field(
        default=None,
        description="Model name",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name for API key",
    )
    api_rate_limit: int = Field(
        default=60,
        description="Maximum requests per minute for API",
    )

    # Ollama backend options
    ollama_model: str | None = Field(
        default="llama3",
        description="Ollama model name",
    )
    ollama_url: str | None = Field(
        default="http://localhost:11434",
        description="Ollama base URL",
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
