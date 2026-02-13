"""Tests for Claude Adapter."""
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.backends.base import AnalysisResult
from lantern_cli.backends.claude import ClaudeAdapter


class TestClaudeAdapter:
    """Test ClaudeAdapter."""

    @pytest.fixture
    def adapter(self) -> ClaudeAdapter:
        """Create a ClaudeAdapter instance."""
        return ClaudeAdapter(model="claude-3-opus", api_key_env="ANTHROPIC_API_KEY")

    def test_health_check_success(self, adapter: ClaudeAdapter) -> None:
        """Test health check (mocked)."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
            assert adapter.health_check() is True

    def test_health_check_failure(self, adapter: ClaudeAdapter) -> None:
        """Test health check failure when key missing."""
        with patch.dict("os.environ", {}, clear=True):
            assert adapter.health_check() is False

    @patch("lantern_cli.backends.claude.ClaudeAdapter._call_api")
    def test_analyze_batch(self, mock_call: MagicMock, adapter: ClaudeAdapter) -> None:
        """Test analyze batch calls API."""
        mock_call.return_value = "Summary: Test\nInsights: A"
        
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
            result = adapter.analyze_batch(["file.py"], "", "prompt")
            
        assert isinstance(result, AnalysisResult)
        assert "Test" in result.summary


