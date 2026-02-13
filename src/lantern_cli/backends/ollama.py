"""Ollama backend adapter."""

from typing import Any

from lantern_cli.backends.base import BackendAdapter

try:
    from langchain_ollama import ChatOllama
    _CHAT_OLLAMA_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - tested via patching sentinel
    ChatOllama = None
    _CHAT_OLLAMA_IMPORT_ERROR = exc


class OllamaBackend(BackendAdapter):
    """Backend adapter for Ollama (local LLMs)."""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        """Initialize Ollama backend configuration."""
        self.model = model
        self.base_url = base_url.rstrip("/")

    def get_llm(self) -> Any:
        """Create a LangChain ChatOllama client from backend config."""
        if ChatOllama is None:
            raise RuntimeError(
                "langchain-ollama is required to use OllamaBackend.get_llm(); "
                "install it with: pip install langchain-ollama"
            ) from _CHAT_OLLAMA_IMPORT_ERROR

        return ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=0,
        )
