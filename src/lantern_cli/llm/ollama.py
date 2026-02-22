"""Ollama backend - minimal factory.

Deep LangChain binding. Responsible only for initialization.
"""

from typing import Any

try:
    from langchain_ollama import ChatOllama

    _CHAT_OLLAMA_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    ChatOllama = None
    _CHAT_OLLAMA_IMPORT_ERROR = exc


def create_ollama_llm(
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    num_predict: int | None = None,
) -> Any:
    """Create ChatOllama LLM instance.

    Returns a ChatModel directly (not a chain). Callers can:
    - Call .invoke() or .batch() directly for simple text generation
    - Call .with_structured_output() to enforce schema for structured output

    Args:
        model: Ollama model name.
        base_url: Ollama server URL.
        num_predict: Maximum number of tokens to generate. None uses model default.

    Returns:
        Configured ChatOllama instance.

    Raises:
        RuntimeError: If langchain-ollama not installed.
    """
    if ChatOllama is None:
        raise RuntimeError(
            "langchain-ollama is required. Install it with: pip install langchain-ollama"
        ) from _CHAT_OLLAMA_IMPORT_ERROR

    opts: dict[str, Any] = {
        "model": model,
        "base_url": base_url.rstrip("/"),
        "temperature": 0,
    }
    if num_predict is not None:
        opts["num_predict"] = num_predict

    llm = ChatOllama(**opts)

    return llm
