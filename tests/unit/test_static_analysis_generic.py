"""Tests for generic static analysis."""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.static_analysis.generic import GenericAnalyzer


class TestGenericAnalyzer:
    """Test GenericAnalyzer."""

    @pytest.fixture
    def analyzer(self) -> GenericAnalyzer:
        """Create a GenericAnalyzer instance."""
        return GenericAnalyzer()

    def test_extract_imports_python_regex(self, analyzer: GenericAnalyzer, tmp_path: Path) -> None:
        """Test extracting Python imports using regex fallback."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            """
import os
from pathlib import Path
import sys as system
            """
        )

        imports = analyzer.extract_imports(file_path, language="python")
        assert "os" in imports
        assert "pathlib" in imports
        assert "sys" in imports

    def test_extract_imports_js_regex(self, analyzer: GenericAnalyzer, tmp_path: Path) -> None:
        """Test extracting JS/TS imports using regex fallback."""
        file_path = tmp_path / "test.js"
        file_path.write_text(
            """
import { useState } from 'react';
const fs = require('fs');
import React from "react";
            """
        )

        imports = analyzer.extract_imports(file_path, language="javascript")
        assert "react" in imports
        assert "fs" in imports

    def test_ripgrep_installed_check(self, analyzer: GenericAnalyzer) -> None:
        """Test ripgrep availability check."""
        # This might be true or false depending on the environment
        # We just ensure it returns a boolean without error
        assert isinstance(analyzer._is_ripgrep_available(), bool)

    def test_unsupported_language_returns_empty(self, analyzer: GenericAnalyzer, tmp_path: Path) -> None:
        """Test unsupported language returns empty list."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("random content")
        imports = analyzer.extract_imports(file_path, language="unknown")
        assert imports == []

    @patch("subprocess.run")
    def test_ripgrep_extraction(self, mock_run: MagicMock, analyzer: GenericAnalyzer, tmp_path: Path) -> None:
        """Test extraction using ripgrep (mocked)."""
        # Force generic reuse of ripgrep path logic if needed, but here we mock the call
        file_path = tmp_path / "test.py"
        
        # Simulate rg output
        # Format: file:line:content
        mock_run.return_value.stdout = f"{file_path}:1:import os\n{file_path}:2:from pathlib import Path"
        mock_run.return_value.returncode = 0
        
        # Force rg available
        with patch.object(analyzer, "_is_ripgrep_available", return_value=True):
            results = analyzer.grep_imports(tmp_path, "import")
            
        assert len(results) == 2
        assert "import os" in results[0]
        assert "from pathlib import Path" in results[1]

    def test_scan_directory_integration(self, analyzer: GenericAnalyzer, tmp_path: Path) -> None:
        """Test scanning a directory for imports using fallback."""
        # Create a small project structure
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("import A\nimport B")
        (src / "utils.js").write_text("import C from 'lib';")

        # Force rg unavailable to test fallback
        with patch.object(analyzer, "_is_ripgrep_available", return_value=False):
            results = analyzer.grep_imports(tmp_path, "import")
        
        assert len(results) >= 3
        # Results format: path:line:content
        content_found = [r.split(":", 2)[2] for r in results]
        assert "import A" in content_found
        assert "import B" in content_found
        assert "import C from 'lib';" in content_found
