"""OpenAI backend - direct API support.

Deep LangChain binding. Uses official OpenAI API directly (not through OpenRouter).
Provides access to all OpenAI models including GPT-4o, GPT-4o-mini, etc.

Recommended models for production:
- gpt-4o-mini: Fastest and cheapest, good for batch analysis
- gpt-4o: Higher quality, good for synthesis
"""

from __future__ import annotations

import os
from typing import Any

try:
    from langchain_openai import ChatOpenAI

    _CHAT_OPENAI_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    ChatOpenAI = None
    _CHAT_OPENAI_IMPORT_ERROR = exc

from ..config.models import BackendConfig


def create_openai_chat(config: BackendConfig, **kwargs: Any) -> Any:
    """Create a LangChain ChatModel configured to use OpenAI API directly.

    Returns a ChatModel directly (not a chain). Callers can:
    - Call .invoke() or .batch() directly for simple text generation
    - Call .with_structured_output() to enforce schema for structured output

    Uses official OpenAI API with direct API key authentication.

    Args:
        config: BackendConfig with openai_* fields.
        **kwargs: Additional arguments passed to ChatOpenAI.

    Returns:
        Configured ChatOpenAI instance.

    Raises:
        RuntimeError: If langchain-openai not installed or API key missing.
    """
    if ChatOpenAI is None:
        raise RuntimeError(
            "langchain-openai is required. Install it with: pip install langchain-openai"
        ) from _CHAT_OPENAI_IMPORT_ERROR

    # Get API key from environment variable
    api_key_env = config.openai_api_key_env or "OPENAI_API_KEY"
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"OpenAI API key not found in env var {api_key_env}. "
            f"Set it with: export {api_key_env}=<your-api-key>"
        )

    # OpenAI model identifier (e.g., "gpt-4o-mini", "gpt-4o")
    model_name = config.openai_model or "gpt-4o-mini"

    # Initialize ChatOpenAI with official API
    # No base_url needed - uses default OpenAI endpoint
    client = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
        **kwargs,
    )

    return client
