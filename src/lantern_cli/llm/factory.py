"""LLM backend factory.

Creates a ``Backend`` instance from configuration.  LangChain-based
providers (OpenAI, Ollama, OpenRouter) are wrapped in
``LangChainBackend``; the CLI provider uses ``CLIBackend`` directly;
the ``openai_sdk`` provider uses the ``openai`` package directly via
``OpenAISDKBackend`` (compatible with OpenAI Agents SDK).

Example:
    config = load_config()
    backend = create_backend(config)
    response = backend.invoke("Hello")
    print(response.content)
"""

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING, Any

from lantern_cli.llm.backend import Backend
from lantern_cli.llm.backends.cli_backend import CLIBackend
from lantern_cli.llm.backends.langchain_backend import LangChainBackend
from lantern_cli.llm.backends.openai_sdk_backend import OpenAISDKBackend
from lantern_cli.llm.ollama import create_ollama_llm
from lantern_cli.llm.openai import create_openai_chat
from lantern_cli.llm.openrouter import create_openrouter_chat

if TYPE_CHECKING:
    from lantern_cli.config.models import LanternConfig


def create_backend(config: LanternConfig, **kwargs: Any) -> Backend:
    """Create a Backend instance from configuration.

    Dispatches to provider-specific factory based on ``config.backend.type``.

    Args:
        config: LanternConfig object with backend configuration.

    Returns:
        A ``Backend`` instance ready for ``invoke()`` /
        ``batch_invoke_structured()`` calls.

    Raises:
        ValueError: If backend type is not recognised or supported.
        RuntimeError: If required provider package is not installed.
    """
    backend_config = config.backend

    # ---- CLI backend (no LangChain dependency) ----
    if backend_config.type == "cli":
        command = shlex.split(backend_config.cli_command or "codex exec")
        return CLIBackend(
            command=command,
            model=backend_config.cli_model_name or "cli",
        )

    # ---- OpenAI SDK backend (no LangChain dependency) ----
    if backend_config.type == "openai_sdk":
        api_key_env = backend_config.openai_sdk_api_key_env or "OPENAI_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"API key not found in env var {api_key_env}. "
                f"Set it with: export {api_key_env}=<your-api-key>"
            )
        return OpenAISDKBackend(
            api_key=api_key,
            model=backend_config.openai_sdk_model or "gpt-4o-mini",
            base_url=backend_config.openai_sdk_base_url,
        )

    # ---- LangChain-based backends ----
    if backend_config.type == "ollama":
        chat_model = create_ollama_llm(
            model=backend_config.ollama_model or "llama3",
            base_url=backend_config.ollama_url or "http://localhost:11434",
        )
        model_name = backend_config.ollama_model or "llama3"
    elif backend_config.type == "openai":
        chat_model = create_openai_chat(backend_config, **kwargs)
        model_name = backend_config.openai_model or "gpt-4o-mini"
    elif backend_config.type == "openrouter":
        chat_model = create_openrouter_chat(backend_config, **kwargs)
        model_name = backend_config.openrouter_model or "openai/gpt-4o-mini"
    elif backend_config.type == "api":
        raise NotImplementedError("API provider not implemented")
    else:
        raise ValueError(f"Unsupported backend type: {backend_config.type}")

    return LangChainBackend(chat_model, model=model_name)
