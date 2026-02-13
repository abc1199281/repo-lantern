"""Tests for Gemini Adapter."""
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.backends.base import AnalysisResult
from lantern_cli.backends.gemini import GeminiAdapter


class TestGeminiAdapter:
    """Test GeminiAdapter."""

    @pytest.fixture
    def adapter(self) -> GeminiAdapter:
        """Create a GeminiAdapter instance."""
        return GeminiAdapter(model="gemini-1.5-pro", api_key_env="GEMINI_API_KEY")

    def test_health_check_success(self, adapter: GeminiAdapter) -> None:
        """Test health check (mocked)."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            assert adapter.health_check() is True

    def test_health_check_failure(self, adapter: GeminiAdapter) -> None:
        """Test health check failure when key missing."""
        with patch.dict("os.environ", {}, clear=True):
            assert adapter.health_check() is False

    @patch("lantern_cli.backends.gemini.GeminiAdapter._call_api")
    def test_analyze_batch(self, mock_call: MagicMock, adapter: GeminiAdapter) -> None:
        """Test analyze batch calls API."""
        mock_call.return_value = "Summary: Test\nInsights: A"
        
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            result = adapter.analyze_batch(["file.py"], "", "prompt")
            
        assert isinstance(result, AnalysisResult)
        assert "Test" in result.summary
        assert result.raw_output == "Summary: Test\nInsights: A"
