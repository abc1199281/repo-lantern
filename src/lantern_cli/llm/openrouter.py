"""OpenRouter backend - minimal factory.

Deep LangChain binding. Responsible only for initialization and OpenRouter
API key management.

OpenRouter is compatible with the OpenAI API surface, so we use ChatOpenAI
with environment-based API key configuration pointing to the OpenRouter endpoint.
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


def create_openrouter_chat(config: BackendConfig, **kwargs: Any) -> Any:
    """Create a LangChain ChatModel configured to use OpenRouter.

    Returns a ChatModel directly (not a chain). Callers can:
    - Call .invoke() or .batch() directly for simple text generation
    - Call .with_structured_output() to enforce schema for structured output

    OpenRouter is OpenAI API-compatible, so we use ChatOpenAI with the
    OpenRouter base URL and API key from environment variables.

    Args:
        config: BackendConfig with openrouter_* fields.
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

    api_key_env = config.openrouter_api_key_env or "OPENROUTER_API_KEY"
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"OpenRouter API key not found in env var {api_key_env}. "
            f"Set it with: export {api_key_env}=<your-api-key>"
        )

    # OpenRouter endpoint URL (usually https://openrouter.ai/api/v1)
    base_url = config.openrouter_url or "https://openrouter.ai/api/v1"

    # OpenRouter model identifier (e.g., "openai/gpt-4-turbo")
    model_name = config.openrouter_model or "openai/gpt-3.5-turbo"

    # Initialize ChatOpenAI with OpenRouter credentials.
    client = ChatOpenAI(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        **kwargs,
    )

    return client
