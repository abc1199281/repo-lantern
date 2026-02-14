"""Tests for create_ollama_llm factory function."""

from unittest.mock import patch

import pytest

from lantern_cli.llm.ollama import create_ollama_llm


def test_create_ollama_llm_constructs_chatollama() -> None:
    """create_ollama_llm returns ChatOllama instance."""
    with patch("lantern_cli.llm.ollama.ChatOllama") as mock_chat:
        llm = create_ollama_llm(model="qwen3:8b", base_url="http://localhost:11434")

    assert llm is mock_chat.return_value
    mock_chat.assert_called_once_with(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0,
    )


def test_create_ollama_llm_raises_runtime_error_when_langchain_ollama_missing() -> None:
    """Raise actionable error when langchain-ollama dependency is missing."""
    with patch("lantern_cli.llm.ollama.ChatOllama", None), patch(
        "lantern_cli.llm.ollama._CHAT_OLLAMA_IMPORT_ERROR", ImportError("missing")
    ):
        with pytest.raises(RuntimeError, match="pip install langchain-ollama"):
            create_ollama_llm(model="qwen3:8b", base_url="http://localhost:11434")


def test_create_ollama_llm_trims_base_url() -> None:
    """Use stripped base_url (without trailing slash)."""
    with patch("lantern_cli.llm.ollama.ChatOllama") as mock_chat:
        create_ollama_llm(model="qwen3:8b", base_url="http://localhost:11434/")

    mock_chat.assert_called_once_with(
        model="qwen3:8b",
        base_url="http://localhost:11434",
        temperature=0,
    )
