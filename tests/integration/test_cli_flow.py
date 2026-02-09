"""Integration tests for Lantern CLI flow."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lantern_cli.cli.main import app
from lantern_cli.backends.base import AnalysisResult


class TestCLIFlow:
    """End-to-end CLI flow tests."""

    @pytest.fixture
    def mock_components(self):
        """Mock all major components."""
        with patch("lantern_cli.cli.main.DependencyGraph") as mock_graph, \
             patch("lantern_cli.cli.main.Architect") as mock_architect, \
             patch("lantern_cli.cli.main.StateManager") as mock_state, \
             patch("lantern_cli.cli.main.Runner") as mock_runner, \
             patch("lantern_cli.cli.main.Synthesizer") as mock_synth, \
             patch("lantern_cli.cli.main.BackendFactory") as mock_factory, \
             patch("lantern_cli.cli.main.load_config") as mock_config:
            
            # Setup mocks
            mock_architect_inst = mock_architect.return_value
            mock_plan = MagicMock()
            mock_plan.to_markdown.return_value = "# Plan"
            mock_architect_inst.generate_plan.return_value = mock_plan
            
            mock_state_inst = mock_state.return_value
            # Return one batch then empty
            batch = MagicMock()
            batch.id = 1
            batch.files = ["test.py"]
            mock_state_inst.get_pending_batches.side_effect = [[batch], []]
            
            mock_runner_inst = mock_runner.return_value
            mock_runner_inst.run_batch.return_value = True
            
            yield {
                "graph": mock_graph,
                "architect": mock_architect,
                "state": mock_state,
                "runner": mock_runner,
                "synth": mock_synth,
                "factory": mock_factory,
                "config": mock_config
            }

    def test_lantern_run_flow(self, mock_components, tmp_path):
        """Test the full 'lantern run' execution flow."""
        runner = CliRunner()
        
        # Invoke CLI
        result = runner.invoke(app, ["run", "--repo", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Lantern Analysis" in result.stdout
        assert "Repository:" in result.stdout
        
        # Verify component interactions
        mocks = mock_components
        
        # 1. Config loading
        mocks["config"].assert_called()
        
        # 2. Backward compatibility / Factory init
        mocks["factory"].create.assert_called()
        
        # 3. Static Analysis
        mocks["graph"].assert_called()
        mocks["graph"].return_value.build.assert_called()
        
        # 4. Architect Plan
        mocks["architect"].assert_called()
        mocks["architect"].return_value.generate_plan.assert_called()
        
        # 5. Runner Loop
        mocks["state"].assert_called()
        mocks["runner"].assert_called()
        mocks["runner"].return_value.run_batch.assert_called()
        
        # 6. Synthesizer
        mocks["synth"].assert_called()
        mocks["synth"].return_value.generate_top_down_docs.assert_called()

    def test_lantern_init(self, tmp_path):
        """Test 'lantern init' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["init", "--repo", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Initialized Lantern" in result.stdout
        
        # Check files
        lantern_dir = tmp_path / ".lantern"
        assert lantern_dir.exists()
        assert (lantern_dir / "lantern.toml").exists()

    def test_lantern_plan(self, mock_components, tmp_path):
        """Test 'lantern plan' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--repo", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Plan generated successfully" in result.stdout
        
        # Verify interactions
        mocks = mock_components
        mocks["graph"].assert_called()
        mocks["architect"].assert_called()
        mocks["architect"].return_value.generate_plan.assert_called()
        
        # Ensure Runner was NOT called
        mocks["runner"].assert_not_called()
