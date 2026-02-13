"""Tests for Runner module."""
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from lantern_cli.backends.base import BackendAdapter, AnalysisResult
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import StateManager, ExecutionState
from lantern_cli.core.architect import Batch


class TestRunner:
    """Test Runner class."""

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        """Create a mock backend adapter."""
        backend = MagicMock(spec=BackendAdapter)
        backend.analyze_batch.return_value = AnalysisResult(
            summary="Test Summary",
            key_insights=["Insight 1"],
            questions=[],
            raw_output="Raw"
        )
        return backend

    @pytest.fixture
    def mock_state_manager(self) -> MagicMock:
        """Create a mock state manager."""
        state_manager = MagicMock(spec=StateManager)
        state_manager.state = ExecutionState(global_summary="Old Summary")
        return state_manager

    @pytest.fixture
    def runner(self, mock_backend: MagicMock, mock_state_manager: MagicMock, tmp_path: Path) -> Runner:
        """Create a Runner instance."""
        return Runner(
            root_path=tmp_path,
            backend=mock_backend,
            state_manager=mock_state_manager
        )

    def test_run_batch_success(self, runner: Runner, mock_backend: MagicMock, mock_state_manager: MagicMock) -> None:
        """Test successful batch execution."""
        batch = Batch(id=1, files=["file1.py"])
        
        # Mock file writing
        with patch("builtins.open", mock_open()) as mock_file:
            success = runner.run_batch(batch, "Prompt")
            
        assert success
        
        # Verify backend call
        mock_backend.analyze_batch.assert_called_once()
        args = mock_backend.analyze_batch.call_args
        assert args[1]["context"] == "Old Summary"  # Check Temporal RAG injection
        
        # Verify state update
        mock_state_manager.update_batch_status.assert_called_with(1, success=True)
        # Verify global summary update (should pass new content only)
        mock_state_manager.update_global_summary.assert_called_with("Batch 1 Summary:\nTest Summary")
        
        # Verify bottom-up doc generation (simple check if open called enough times)
        # 1 call for .sense, 1 call for .md
        assert mock_file.call_count >= 2

    def test_run_batch_failure(self, runner: Runner, mock_backend: MagicMock, mock_state_manager: MagicMock) -> None:
        """Test failed batch execution."""
        batch = Batch(id=1, files=["file1.py"])
        mock_backend.analyze_batch.side_effect = Exception("API Error")
        
        success = runner.run_batch(batch, "Prompt")
        assert not success
        
        # Verify state update
        mock_state_manager.update_batch_status.assert_called_with(1, success=False)

    def test_context_injection(self, runner: Runner) -> None:
        """Test that global summary is strictly size-limited."""
        context = runner._prepare_context()
        assert "Old Summary" in context
        
        # Test truncation logic if implemented
        long_summary = "A" * 5000
        runner.state_manager.state.global_summary = long_summary
        context_long = runner._prepare_context()
        assert len(context_long) <= 4000  # Assuming 4000 char limit or similar
