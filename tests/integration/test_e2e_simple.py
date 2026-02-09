"""End-to-end simple integration test."""
import os
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from lantern_cli.cli.main import app

class TestE2ESimple:
    """Simple end-to-end test using a temporary directory."""

    @pytest.fixture
    def repo_path(self, tmp_path):
        """Create a dummy repository structure."""
        # Create src directory
        src = tmp_path / "src"
        src.mkdir()
        
        # Create a simple python file
        (src / "main.py").write_text("""
def main():
    print("Hello World")

if __name__ == "__main__":
    main()
""")
        
        # Create a utility file
        (src / "utils.py").write_text("""
def helper():
    return True
""")
        return tmp_path

    @patch("lantern_cli.backends.factory.BackendFactory.create")
    def test_full_workflow(self, mock_backend_create, repo_path):
        """Test init -> plan -> run workflow."""
        runner = CliRunner()
        
        # 1. Initialize
        result = runner.invoke(app, ["init", "--repo", str(repo_path)])
        assert result.exit_code == 0
        assert (repo_path / ".lantern" / "lantern.toml").exists()

        # 2. Plan
        result = runner.invoke(app, ["plan", "--repo", str(repo_path)])
        if result.exit_code != 0:
            print(result.stdout)
            import traceback
            traceback.print_exception(*result.exc_info)
        assert result.exit_code == 0
        assert (repo_path / ".lantern" / "lantern_plan.md").exists()
        
        # 3. Run
        # Mock backend response to avoid API calls
        mock_backend = MagicMock()
        mock_result = MagicMock()
        mock_result.summary = "Analysis Summary"
        mock_result.key_insights = ["Insight 1", "Insight 2"]
        mock_result.raw_output = "Raw output"
        mock_result.questions = []
        mock_backend.analyze_batch.return_value = mock_result
        mock_backend_create.return_value = mock_backend

        result = runner.invoke(app, ["run", "--repo", str(repo_path)])
        
        assert result.exit_code == 0
        assert "Analysis Complete" in result.stdout
        
        # Verify outputs
        output_dir = repo_path / ".lantern" / "output" / "en"
        
        # Top-down docs
        assert (output_dir / "top_down" / "OVERVIEW.md").exists()
        assert (output_dir / "top_down" / "ARCHITECTURE.md").exists()
        
        # Bottom-up docs
        # Should mirror src structure
        assert (output_dir / "bottom_up" / "src" / "main.py.md").exists()
        assert (output_dir / "bottom_up" / "src" / "utils.py.md").exists()
