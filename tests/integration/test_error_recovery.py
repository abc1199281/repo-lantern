"""Integration test for error recovery and resume logic."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from lantern_cli.cli.main import app
from lantern_cli.core.state_manager import StateManager
from lantern_cli.llm.structured import StructuredAnalysisOutput

class TestErrorRecovery:
    """Test resume capability after failure."""

    @pytest.fixture
    def repo_path(self, tmp_path):
        """Create a dummy repository structure."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('main')")
        (src / "utils.py").write_text("print('utils')")
        return tmp_path

    @patch("lantern_cli.core.runner.StructuredAnalyzer")
    @patch("lantern_cli.backends.factory.BackendFactory.create")
    def test_resume_after_failure(self, mock_backend_create, mock_structured_analyzer, repo_path):
        """Test that failed batches are retried on next run."""
        runner = CliRunner()
        
        # 0. Init
        runner.invoke(app, ["init", "--repo", str(repo_path)])
        
        # 1. First Run: Fail on Batch 1
        # Mock backend to fail for the first call
        mock_backend = MagicMock()
        
        # Setup side effect for analyze_batch
        # We expect 1 batch (Batch 1) containing all files (since small repo)
        # Or maybe multiple batches. Let's see.
        # Architect uses BATCH_SIZE=3. Here we have 2 files. So 1 batch.
        # Let's force Architect to use BATCH_SIZE=1 for this test 
        # But we can't easily patch class attribute inside integration test without patching Architect class
        # Ideally, we want 2 batches to test partial success.
        
        # We can create more files to force multiple batches
        (repo_path / "src" / "a.py").write_text("a")
        (repo_path / "src" / "b.py").write_text("b")
        (repo_path / "src" / "c.py").write_text("c")
        # Now we have main, utils, a, b, c = 5 files.
        # Batch 1: 3 files. Batch 2: 2 files.
        
        # Let's make Batch 1 fail, Batch 2 succeed (if run continues).
        # Actually main.py continues on failure.
        
        def side_effect(files, context, prompt):
            # Hacky way to distinguish batches by files
            if "a.py" in files[0] or "main.py" in files[0]: # Batch 1 likely contains main or a
                 # We want this to fail
                 raise Exception("Simulated Backend Failure")
            return MagicMock(summary="Success", raw_output="raw", key_insights=[])

        mock_backend.analyze_batch.side_effect = side_effect
        mock_backend.get_llm.return_value = MagicMock()
        mock_backend_create.return_value = mock_backend

        analyzer = MagicMock()
        analyzer.analyze_batch.return_value = [
            StructuredAnalysisOutput(summary="s1", key_insights=[], language="en"),
            StructuredAnalysisOutput(summary="s2", key_insights=[], language="en"),
            StructuredAnalysisOutput(summary="s3", key_insights=[], language="en"),
        ]
        mock_structured_analyzer.return_value = analyzer

        result = runner.invoke(app, ["run", "--repo", str(repo_path), "--yes"])
        
        # It should exit 0 because run() catches errors? 
        # No, run() prints "Batch X failed" but continues.
        
        # Verify state
        state_manager = StateManager(repo_path)
        state_manager.load_state() # Reload
        
        # We expect some failure
        assert len(state_manager.state.failed_batches) > 0 or len(state_manager.state.completed_batches) < 2
        
        # 2. Second Run: Succeed
        # Reset mock to always succeed
        mock_backend.analyze_batch.side_effect = None
        mock_backend.analyze_batch.return_value = MagicMock(
            summary="Recovered", raw_output="recovered", key_insights=[]
        )
        
        result = runner.invoke(app, ["run", "--repo", str(repo_path), "--yes"])
        
        # Verify "Processing X batches..." message indicates only pending batches were run
        # How to verify? Check stdout or mock call count.
        
        # If Batch 1 failed, it should be retried.
        # Batch 2 passed, so it should NOT be retried.
        
        # Using state to verify
        state_manager = StateManager(repo_path)
        # Force reload from disk
        state_manager.state = state_manager.load_state() 
        
        assert len(state_manager.state.failed_batches) == 0
        assert len(state_manager.state.completed_batches) >= 2
