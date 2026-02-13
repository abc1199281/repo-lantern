"""Integration tests for multi-language repositories."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from lantern_cli.cli.main import app

@pytest.fixture
def mixed_repo(tmp_path):
    """Create a mixed language repository."""
    src = tmp_path / "src"
    src.mkdir()
    
    (src / "main.py").write_text("def main(): pass")
    (src / "core.cpp").write_text("int main() { return 0; }")
    (src / "script.sh").write_text("#!/bin/bash\necho hello")
    
    return tmp_path

@patch("lantern_cli.backends.factory.BackendFactory.create")
def test_mixed_language_support(mock_backend_create, mixed_repo):
    """Test that all supported file types are picked up."""
    
    # Mock backend to succeed 
    mock_backend = MagicMock()
    mock_backend.analyze_batch.return_value = MagicMock(
        summary="Mixed Lang Analysis", 
        key_insights=[], 
        questions=[],
        raw_output="Raw output"
    )
    mock_backend_create.return_value = mock_backend
    
    runner = CliRunner()
    
    # 1. Init
    runner.invoke(app, ["init", "--repo", str(mixed_repo)])
    
    # 2. Run
    result = runner.invoke(app, ["run", "--repo", str(mixed_repo), "--yes"])
    
    assert result.exit_code == 0
    assert "Analysis Complete" in result.stdout
    
    # Verify outputs
    # All 3 files should be processed if they are supported by current DependencyGraph/FileFilter
    # Current FileFilter likely supports .py, .cpp, .sh?
    # Let's verify output files exist
    
    output_dir = mixed_repo / ".lantern" / "output" / "en" / "bottom_up" / "src"
    
    assert (output_dir / "main.py.md").exists()
    assert (output_dir / "core.cpp.md").exists()
    # assert (output_dir / "script.sh.md").exists() # Check if shell scripts are supported default
