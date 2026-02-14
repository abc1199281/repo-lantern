from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from lantern_cli.llm.factory import create_llm
from lantern_cli.config.models import BackendConfig, LanternConfig


class TestBackendFactory:
    """Test LLM factory."""

    def test_create_api_not_implemented(self) -> None:
        """API backend is not implemented yet."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="gemini",
                api_model="custom-gemini"
            )
        )
        with pytest.raises(NotImplementedError):
            create_llm(config)

    def test_create_unknown_backend(self) -> None:
        """Test creating unknown backend type raises ValidationError."""
        with pytest.raises(ValidationError):
            BackendConfig(type="unknown-backend-type")  # type: ignore[arg-type]
