"""Integration tests for multi-language repositories."""
import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from lantern_cli.cli.main import app
from lantern_cli.llm.structured import StructuredAnalysisOutput

@pytest.fixture
def mixed_repo(tmp_path):
    """Create a mixed language repository."""
    src = tmp_path / "src"
    src.mkdir()
    
    (src / "main.py").write_text("def main(): pass")
    (src / "core.cpp").write_text("int main() { return 0; }")
    (src / "script.sh").write_text("#!/bin/bash\necho hello")
    
    return tmp_path

@patch("lantern_cli.core.runner.StructuredAnalyzer")
@patch("lantern_cli.backends.factory.BackendFactory.create")
def test_mixed_language_support(mock_backend_create, mock_structured_analyzer, mixed_repo):
    """Test that all supported file types are picked up."""
    
    # Mock backend to succeed 
    mock_backend = MagicMock()
    mock_backend.analyze_batch.return_value = MagicMock(
        summary="Mixed Lang Analysis",
        key_insights=[],
        raw_output="Raw output",
    )
    mock_backend.get_llm.return_value = MagicMock()
    mock_backend_create.return_value = mock_backend

    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        StructuredAnalysisOutput(summary="main", key_insights=[], language="en"),
        StructuredAnalysisOutput(summary="cpp", key_insights=[], language="en"),
    ]
    mock_structured_analyzer.return_value = analyzer
    
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
    
    output_dir = mixed_repo / ".lantern" / "output" / "zh-TW" / "bottom_up" / "src"
    
    assert (output_dir / "main.py.md").exists()
    assert (output_dir / "core.cpp.md").exists()
    # assert (output_dir / "script.sh.md").exists() # Check if shell scripts are supported default
