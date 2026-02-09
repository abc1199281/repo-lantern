"""Tests for FileFilter."""
import shutil
import tempfile
from pathlib import Path

import pytest
from pathspec import PathSpec

from lantern_cli.config.models import FilterConfig
from lantern_cli.static_analysis.file_filter import FileFilter


class TestFileFilter:
    """Test FileFilter."""

    @pytest.fixture
    def filter_config(self) -> FilterConfig:
        """Create a default filter config."""
        return FilterConfig(
            exclude=["*.tmp", "build/"],
            include=["important.tmp"]
        )

    @pytest.fixture
    def file_filter(self, filter_config: FilterConfig) -> FileFilter:
        """Create a FileFilter instance."""
        return FileFilter(root_path=Path("/tmp"), config=filter_config)

    def test_default_excludes(self, file_filter: FileFilter) -> None:
        """Test default exclude rules."""
        assert file_filter.should_ignore(Path("node_modules/package.json"))
        assert file_filter.should_ignore(Path(".git/config"))
        assert file_filter.should_ignore(Path("dist/bundle.js"))
        assert file_filter.should_ignore(Path("test.map"))
        assert not file_filter.should_ignore(Path("src/main.py"))

    def test_custom_excludes(self, file_filter: FileFilter) -> None:
        """Test custom exclude rules from config."""
        assert file_filter.should_ignore(Path("temp.tmp"))
        assert file_filter.should_ignore(Path("build/output.txt"))

    def test_include_overrides(self, file_filter: FileFilter) -> None:
        """Test include rules override exclude rules."""
        # "important.tmp" is both excluded via *.tmp and included via config
        # Include should win
        assert not file_filter.should_ignore(Path("important.tmp"))

    def test_gitignore_parsing(self, tmp_path: Path) -> None:
        """Test parsing .gitignore files."""
        # Create a temp directory with .gitignore
        (tmp_path / ".gitignore").write_text("ignored.txt\nsecret/")
        (tmp_path / "secret").mkdir()
        
        file_filter = FileFilter(root_path=tmp_path, config=FilterConfig())
        
        assert file_filter.should_ignore(tmp_path / "ignored.txt")
        assert file_filter.should_ignore(tmp_path / "secret/file.txt")
        assert not file_filter.should_ignore(tmp_path / "normal.txt")

    def test_walk_files(self, tmp_path: Path) -> None:
        """Test walking files with filtering."""
        # Setup structure
        # root/
        #   .gitignore (secret/)
        #   src/
        #     main.py
        #   secret/
        #     key.pem
        #   node_modules/
        #     pkg/
        #       index.js
        
        gw = tmp_path / ".gitignore"
        gw.write_text("secret/")
        
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        
        (tmp_path / "secret").mkdir()
        (tmp_path / "secret" / "key.pem").write_text("key")
        
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("code")
        
        file_filter = FileFilter(root_path=tmp_path, config=FilterConfig())
        
        files = list(file_filter.walk())
        rel_files = [str(f.relative_to(tmp_path)) for f in files]
        
        assert "src/main.py" in rel_files
        assert "secret/key.pem" not in rel_files
        assert ".gitignore" in rel_files # .gitignore itself is not ignored by default unless specified
        # node_modules should be ignored by default rules
        assert not any("node_modules" in f for f in rel_files)
