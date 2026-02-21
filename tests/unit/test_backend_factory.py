from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from lantern_cli.config.models import BackendConfig, LanternConfig
from lantern_cli.llm.backends.cli_backend import CLIBackend
from lantern_cli.llm.backends.langchain_backend import LangChainBackend
from lantern_cli.llm.factory import create_backend


class TestBackendFactory:
    """Test backend factory."""

    def test_create_api_not_implemented(self) -> None:
        """API backend is not implemented yet."""
        config = LanternConfig(
            backend=BackendConfig(type="api", api_provider="gemini", api_model="custom-gemini")
        )
        with pytest.raises(NotImplementedError):
            create_backend(config)

    def test_create_unknown_backend(self) -> None:
        """Test creating unknown backend type raises ValidationError."""
        with pytest.raises(ValidationError):
            BackendConfig(type="unknown-backend-type")  # type: ignore[arg-type]

    def test_create_cli_backend(self) -> None:
        """Test creating CLI backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="cli",
                cli_command="echo hello",
                cli_model_name="test-cli",
            )
        )
        backend = create_backend(config)
        assert isinstance(backend, CLIBackend)
        assert backend.model_name == "test-cli"

    def test_create_cli_backend_defaults(self) -> None:
        """Test CLI backend with default command."""
        config = LanternConfig(backend=BackendConfig(type="cli"))
        backend = create_backend(config)
        assert isinstance(backend, CLIBackend)
        assert backend.model_name == "cli"

    @patch("lantern_cli.llm.factory.create_ollama_llm")
    def test_create_ollama_returns_langchain_backend(self, mock_create: MagicMock) -> None:
        """Test that ollama type returns a LangChainBackend wrapper."""
        mock_create.return_value = MagicMock()
        config = LanternConfig(backend=BackendConfig(type="ollama", ollama_model="llama3"))
        backend = create_backend(config)
        assert isinstance(backend, LangChainBackend)
        assert backend.model_name == "llama3"
