"""Tests for BackendAdapter.invoke via OllamaBackend.get_llm."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lantern_cli.backends.ollama import OllamaBackend


def test_invoke_returns_plain_text() -> None:
    llm = MagicMock()
    llm.invoke.return_value = SimpleNamespace(
        content="Summary line\n- First insight\n- Second insight"
    )

    backend = OllamaBackend(model="qwen3:8b", base_url="http://localhost:11434")
    with patch.object(backend, "get_llm", return_value=llm):
        out = backend.invoke("Analyze this batch.")

    assert out.startswith("Summary line")
    llm.invoke.assert_called_once()


def test_invoke_handles_list_content() -> None:
    llm = MagicMock()
    llm.invoke.return_value = SimpleNamespace(content=["a", "b"])
    backend = OllamaBackend(model="qwen3:8b", base_url="http://localhost:11434")

    with patch.object(backend, "get_llm", return_value=llm):
        out = backend.invoke("Analyze")

    assert out == "a\nb"
