"""Tests for Codex Adapter."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from lantern_cli.backends.base import AnalysisResult
from lantern_cli.backends.codex import CodexAdapter


class TestCodexAdapter:
    """Test CodexAdapter."""

    @pytest.fixture
    def adapter(self) -> CodexAdapter:
        """Create a CodexAdapter instance."""
        return CodexAdapter()

    @patch("shutil.which")
    def test_health_check_success(self, mock_which: MagicMock, adapter: CodexAdapter) -> None:
        """Test health check returns True when cli is found."""
        mock_which.return_value = "/bin/codex"
        assert adapter.health_check() is True

    @patch("shutil.which")
    def test_health_check_failure(self, mock_which: MagicMock, adapter: CodexAdapter) -> None:
        """Test health check returns False when cli is missing."""
        mock_which.return_value = None
        assert adapter.health_check() is False

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_analyze_batch_success(self, mock_run: MagicMock, mock_which: MagicMock, adapter: CodexAdapter) -> None:
        """Test successful batch analysis."""
        mock_which.return_value = "/bin/codex"
        mock_output = """
SUMMARY:
This is a summary.

INSIGHTS:
- Insight 1
- Insight 2

QUESTIONS:
- Question 1
"""
        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        result = adapter.analyze_batch(files=["test.py"], context="", prompt="analyze")
        
        assert isinstance(result, AnalysisResult)
        assert "This is a summary" in result.summary
        assert "Insight 1" in result.key_insights
        assert "Question 1" in result.questions
        assert result.raw_output == mock_output

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_analyze_batch_timeout(self, mock_run: MagicMock, mock_which: MagicMock, adapter: CodexAdapter) -> None:
        """Test timeout handling."""
        mock_which.return_value = "/bin/codex"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=300)
        
        with pytest.raises(RuntimeError, match="CLI analysis timed out"):
            adapter.analyze_batch(files=["test.py"], context="", prompt="analyze")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_analyze_batch_failure(self, mock_run: MagicMock, mock_which: MagicMock, adapter: CodexAdapter) -> None:
        """Test CLI failure handling."""
        mock_which.return_value = "/bin/codex"
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="codex", stderr="Error")
        
        with pytest.raises(RuntimeError, match="CLI analysis failed"):
            adapter.analyze_batch(files=["test.py"], context="", prompt="analyze")
