"""Focused tests for OllamaBackend.get_llm."""

from unittest.mock import patch

import pytest

from lantern_cli.backends.ollama import OllamaBackend


def test_get_llm_constructs_chatollama_with_backend_config() -> None:
    """Build ChatOllama with backend model/base_url/temperature."""
    with patch("lantern_cli.backends.ollama.ChatOllama") as mock_chat:
        backend = OllamaBackend(model="qwen3:8b", base_url="http://localhost:11434")
        llm = backend.get_llm()

    assert llm is mock_chat.return_value
    mock_chat.assert_called_once_with(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0,
    )


def test_get_llm_raises_runtime_error_when_langchain_ollama_missing() -> None:
    """Raise actionable error when langchain-ollama dependency is missing."""
    with patch("lantern_cli.backends.ollama.ChatOllama", None), patch(
        "lantern_cli.backends.ollama._CHAT_OLLAMA_IMPORT_ERROR", ImportError("missing")
    ):
        backend = OllamaBackend(model="qwen3:8b", base_url="http://localhost:11434")
        with pytest.raises(RuntimeError, match="pip install langchain-ollama"):
            backend.get_llm()


def test_get_llm_uses_trimmed_base_url_from_init() -> None:
    """Use stripped base_url (without trailing slash)."""
    with patch("lantern_cli.backends.ollama.ChatOllama") as mock_chat:
        backend = OllamaBackend(model="qwen3:8b", base_url="http://localhost:11434/")
        backend.get_llm()

    mock_chat.assert_called_once_with(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0,
    )
