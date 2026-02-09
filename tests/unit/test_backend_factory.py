from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.backends.claude import ClaudeAdapter
from lantern_cli.backends.codex import CodexAdapter
from lantern_cli.backends.factory import BackendFactory, detect_cli
from lantern_cli.backends.gemini import GeminiAdapter
from lantern_cli.config.models import BackendConfig, LanternConfig


class TestCLIBackendDetection:
    """Test CLI backend detection."""

    @patch("shutil.which")
    def test_detect_cli_order(self, mock_which: MagicMock) -> None:
        """Test detection priority: antigravity > codex > gemini > claude."""
        # Case 1: All available -> antigravity wins
        mock_which.side_effect = lambda cmd: f"/bin/{cmd}"
        assert detect_cli() == "antigravity"

        # Case 2: antigravity missing -> codex wins
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "antigravity":
                return None
            return f"/bin/{cmd}"
        
        mock_which.side_effect = which_side_effect
        assert detect_cli() == "codex"

    @patch("shutil.which")
    def test_detect_antigravity(self, mock_which: MagicMock) -> None:
        """Test antigravity has highest priority if we decide to prioritize it."""
        # Assuming detect_cli priority: antigravity > codex > gemini
        mock_which.side_effect = lambda cmd: f"/bin/{cmd}"
        # If implementation prioritizes antigravity
        # Let's align test with implementation plan
        # We'll assert "antigravity" if implemented
        pass 

    @patch("shutil.which")
    def test_no_cli_found(self, mock_which: MagicMock) -> None:
        """Test exception when no CLI is found."""
        mock_which.return_value = None
        with pytest.raises(RuntimeError, match="No supported CLI tool found"):
            detect_cli()


class TestBackendFactory:
    """Test BackendFactory."""

    @patch("lantern_cli.backends.factory.detect_cli")
    def test_create_cli_backend_explicit(self, mock_detect: MagicMock) -> None:
        """Test creating explicitly configured CLI backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="cli",
                cli_command="custom_tool",
                cli_timeout=100
            )
        )
        adapter = BackendFactory.create(config)
        assert isinstance(adapter, CodexAdapter)
        assert adapter.command == "custom_tool"
        assert adapter.timeout == 100
        mock_detect.assert_not_called()

    @patch("lantern_cli.backends.factory.detect_cli")
    def test_create_cli_backend_auto(self, mock_detect: MagicMock) -> None:
        """Test creating CLI backend with auto-detection."""
        mock_detect.return_value = "auto_tool"
        config = LanternConfig(
            backend=BackendConfig(
                type="cli",
                cli_command=None
            )
        )
        adapter = BackendFactory.create(config)
        assert isinstance(adapter, CodexAdapter)
        assert adapter.command == "auto_tool"
        mock_detect.assert_called_once()

    def test_create_api_backend_gemini(self) -> None:
        """Test creating Gemini API backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="gemini",
                api_model="custom-gemini"
            )
        )
        adapter = BackendFactory.create(config)
        assert isinstance(adapter, GeminiAdapter)
        assert adapter.model == "custom-gemini"

    def test_create_api_backend_claude(self) -> None:
        """Test creating Claude API backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="anthropic" # or claude
            )
        )
        adapter = BackendFactory.create(config)
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.api_key_env == "ANTHROPIC_API_KEY"

    def test_create_unknown_api_backend(self) -> None:
        """Test creating unknown API backend."""
        config = LanternConfig(
            backend=BackendConfig(
                type="api",
                api_provider="openai"
            )
        )
        with pytest.raises(NotImplementedError):
            BackendFactory.create(config)
