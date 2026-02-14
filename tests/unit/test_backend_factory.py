from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.backends.factory import BackendFactory
from lantern_cli.config.models import BackendConfig, LanternConfig



class TestBackendFactory:
    """Test BackendFactory."""

    def test_create_api_ollama(self) -> None:
        """API backend is not implemented yet."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="gemini",
                api_model="custom-gemini"
            )
        )
        with pytest.raises(NotImplementedError):
            BackendFactory.create(config)

    def test_create_unknown_api_backend(self) -> None:
        """Test creating unknown API backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="unknown-provider"
            )
        )
        with pytest.raises(NotImplementedError):
            BackendFactory.create(config)
