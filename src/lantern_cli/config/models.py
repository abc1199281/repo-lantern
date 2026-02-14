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

    type: Literal["api", "ollama", "openrouter"] = Field(
        default="ollama",
        description="Backend type: api, ollama, or openrouter",
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

    # OpenRouter backend options
    openrouter_model: str | None = Field(
        default=None,
        description="OpenRouter model identifier",
    )
    openrouter_url: str | None = Field(
        default=None,
        description="OpenRouter base URL",
    )
    openrouter_api_key_env: str | None = Field(
        default="OPENROUTER_API_KEY",
        description="Environment variable name containing OpenRouter API key",
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
