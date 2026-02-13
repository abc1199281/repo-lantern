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
            key_insights=["Insight 1"]
            raw_output="Raw"
        )
        # Per-file analysis returns unique results
        backend.analyze_file.return_value = AnalysisResult(
            summary="File-specific summary",
            key_insights=["File insight"]
            raw_output="Raw file"
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
        
        # Verify batch-level backend call
        mock_backend.analyze_batch.assert_called_once()
        args = mock_backend.analyze_batch.call_args
        assert args[1]["context"] == "Old Summary"  # Check Temporal RAG injection
        
        # Verify per-file analysis call
        mock_backend.analyze_file.assert_called_once()
        
        # Verify state update
        mock_state_manager.update_batch_status.assert_called_with(1, success=True)
        # Verify global summary update (should pass new content only)
        mock_state_manager.update_global_summary.assert_called_with("Batch 1 Summary:\nTest Summary")
        
        # Verify bottom-up doc generation (simple check if open called enough times)
        # 1 call for .sense, 1 call for .md
        assert mock_file.call_count >= 2

    def test_per_file_analysis_produces_unique_docs(self, runner: Runner, mock_backend: MagicMock, tmp_path: Path) -> None:
        """Test that each file in a batch gets its own unique LLM analysis."""
        batch = Batch(id=1, files=[
            str(tmp_path / "module_a.py"),
            str(tmp_path / "module_b.py"),
        ])
        
        # Create dummy source files
        for f in batch.files:
            Path(f).write_text("# dummy", encoding="utf-8")
        
        # Return different results for each file
        results = iter([
            AnalysisResult(summary="Module A handles authentication.", key_insights=["Uses JWT"], raw_output=""),
            AnalysisResult(summary="Module B handles database access.", key_insights=["Uses SQLAlchemy"], raw_output=""),
        ])
        mock_backend.analyze_file.side_effect = lambda **kwargs: next(results)
        mock_backend.analyze_batch.return_value = AnalysisResult(summary="Batch summary", key_insights=[], raw_output="Raw")
        
        runner.run_batch(batch, "Prompt")
        
        # Verify analyze_file was called once per file
        assert mock_backend.analyze_file.call_count == 2
        
        # Verify output files have different content
        bottom_up_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up"
        doc_a = (bottom_up_dir / "module_a.py.md").read_text(encoding="utf-8")
        doc_b = (bottom_up_dir / "module_b.py.md").read_text(encoding="utf-8")
        
        assert "Module A handles authentication" in doc_a
        assert "Module B handles database access" in doc_b
        assert doc_a != doc_b

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
