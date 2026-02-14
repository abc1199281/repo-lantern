"""LLM factory - deeply bound to LangChain.

This module provides LLM instantiation from configuration. No adapter layer -
returns LangChain ChatModel instances directly for use in orchestration logic.

Response Contract:
- All responses must have .content attribute (string or list)
- Optional .usage_metadata dict with 'input_tokens' and 'output_tokens' keys
- cost_tracker.record_from_usage_metadata() handles missing metadata gracefully

Example:
    config = load_config()
    llm = create_llm(config)
    result = llm.invoke([{"role": "user", "content": "..."}])
    print(result.content)  # String or list
"""

from typing import TYPE_CHECKING, Any

from lantern_cli.llm.ollama import create_ollama_llm
from lantern_cli.llm.openrouter import create_openrouter_chat

if TYPE_CHECKING:
    from lantern_cli.config.models import LanternConfig


def create_llm(config: "LanternConfig", **kwargs: Any) -> Any:
    """Create LangChain ChatModel instance from configuration.
    
    Dispatches to provider-specific factory based on backend type.
    Deep binding: returns ChatModel directly without adapter wrapper.
    
    Args:
        config: LanternConfig object with backend configuration.
        
    Returns:
        LangChain ChatModel instance ready for invoke() calls.
        
    Raises:
        ValueError: If backend type is not recognized or supported.
        RuntimeError: If required LangChain provider package not installed.
    """
    backend_config = config.backend
    
    if backend_config.type == "ollama":
        return create_ollama_llm(
            model=backend_config.ollama_model or "llama3",
            base_url=backend_config.ollama_url or "http://localhost:11434"
        )
    elif backend_config.type == "openrouter":
        return create_openrouter_chat(backend_config, **kwargs)
    elif backend_config.type == "api":
        raise NotImplementedError("API provider not implemented")
    else:
        raise ValueError(f"Unsupported backend type: {backend_config.type}")
