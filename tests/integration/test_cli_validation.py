"""Integration tests for CLI validation logic."""
import shutil
from pathlib import Path
from typer.testing import CliRunner
from lantern_cli.cli.main import app

runner = CliRunner()

def test_init_invalid_path():
    """Test 'lantern init' with a file path instead of directory."""
    # This might depend on implementation. 
    # If path doesn't exist, it creates it.
    # If path is a file, mkdir should fail.
    
    with runner.isolated_filesystem():
        # Create a file
        p = Path("existing_file")
        p.write_text("content")
        
        result = runner.invoke(app, ["init", "--repo", "existing_file"])
        
        assert result.exit_code != 0
        assert "Failed to initialize" in result.stdout

def test_run_nonexistent_repo():
    """Test 'lantern run' on non-existent path."""
    result = runner.invoke(app, ["run", "--repo", "/non/existent/path"])
    
    # It might create it or fail? 
    # load_config will fail if excludes logic doesn't handle it
    # DependencyGraph crashes if root doesn't exist?
    # Let's see: DependencyGraph(repo_path...) -> os.walk(repo_path)
    
    # Ideally it should fail gracefully
    assert result.exit_code != 0

def test_run_invalid_backend(tmp_path):
    """Test 'lantern run' with invalid backend type."""
    # Init first
    runner.invoke(app, ["init", "--repo", str(tmp_path)])
    
    # Create a dummy file to ensure there is something to analyze
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.py").write_text("print('hello')")
    
    # Create invalid backend config
    config_path = tmp_path / ".lantern" / "lantern.toml"
    config_content = """
[lantern]
language = "en"
output_dir = ".lantern"

[backend]
type = "cli"
cli_command = "nonexistent_tool"
"""
    config_path.write_text(config_content)
    
    # Run without backend arg (it's removed)
    # We want to verify that it fails gracefully when the tool is not found
    result = runner.invoke(app, ["run", "--repo", str(tmp_path), "--yes"])
    
    # It should fail gracefully (exit code 0 but report failure)
    # Runner catches exceptions and prints failure message
    assert result.exit_code == 0
    assert "Batch 1 failed" in result.stdout or "Error" in result.stdout
    
def test_init_existing_directory_idempotency(tmp_path):
    """Test 'lantern init' on already initialized directory."""
    runner.invoke(app, ["init", "--repo", str(tmp_path)])
    result = runner.invoke(app, ["init", "--repo", str(tmp_path)])
    
    assert result.exit_code == 0
    assert "already initialized" in result.stdout 
