"""Tests for Codex Adapter."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from lantern_cli.backends.base import AnalysisResult
from lantern_cli.backends.cli import CLIAdapter


class TestCLIAdapter:
    """Tests for CLIAdapter."""

    @pytest.fixture
    def adapter(self) -> CLIAdapter:
        """Create a CLIAdapter instance."""
        return CLIAdapter()

    def test_init_defaults(self):
        """Test initialization with defaults."""
        adapter = CLIAdapter()
        assert adapter.command == "cli"
        assert adapter.timeout == 300
        assert adapter.args_template == ["{command}", "exec", "{prompt}"]

    def test_init_custom(self):
        """Test initialization with custom values."""
        adapter = CLIAdapter(
            command="mytool", 
            timeout=60, 
            args_template=["{command}", "{prompt}"]
        )
        assert adapter.command == "mytool"
        assert adapter.timeout == 60
        assert adapter.args_template == ["{command}", "{prompt}"]

    @pytest.fixture
    def mock_env(self):
        """Mock environment with common patches."""
        with patch("lantern_cli.backends.cli.shutil.which") as mock_which, \
             patch("subprocess.run") as mock_run:
            mock_which.return_value = "/usr/bin/cli"
            mock_result = MagicMock()
            mock_result.stdout = "SUMMARY:\nsummary"
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            yield mock_which, mock_run

    def test_health_check_success(self, mock_env) -> None:
        """Test health check when tool exists."""
        mock_which, _ = mock_env
        adapter = CLIAdapter()
        assert adapter.health_check() is True
        mock_which.assert_called_with("cli")

    def test_health_check_failure(self, mock_env) -> None:
        """Test health check when tool missing."""
        mock_which, _ = mock_env
        mock_which.return_value = None
        adapter = CLIAdapter()
        assert adapter.health_check() is False

    def test_analyze_batch_success(self, mock_env) -> None:
        """Test successful analysis with default template."""
        _, mock_run = mock_env
        
        adapter = CLIAdapter()
        result = adapter.analyze_batch(["file1"], "context", "prompt")
        
        assert result.summary == "summary"
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["cli", "exec", "prompt"]

    def test_analyze_batch_custom_template(self, mock_env) -> None:
        """Test analysis with custom template."""
        mock_which, mock_run = mock_env
        mock_which.return_value = "/usr/bin/mytool"
        
        adapter = CLIAdapter(
            command="mytool",
            args_template=["{command}", "--run", "{prompt}"]
        )
        adapter.analyze_batch(["file1"], "context", "prompt")
        
        args = mock_run.call_args[0][0]
        assert args == ["mytool", "--run", "prompt"]

    def test_analyze_batch_timeout(self, mock_env) -> None:
        """Test timeout handling."""
        _, mock_run = mock_env
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="cli", timeout=300)
        
        adapter = CLIAdapter()
        with pytest.raises(RuntimeError, match="CLI analysis timed out"):
            adapter.analyze_batch(files=["test.py"], context="", prompt="analyze")

    def test_analyze_batch_failure(self, mock_env) -> None:
        """Test CLI failure handling."""
        _, mock_run = mock_env
        mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="codex", stderr="Error")
        
        adapter = CLIAdapter()
        with pytest.raises(RuntimeError, match="CLI analysis failed"):
            adapter.analyze_batch(files=["test.py"], context="", prompt="analyze")
