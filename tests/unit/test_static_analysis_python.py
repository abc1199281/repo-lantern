"""Tests for Python static analysis."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.static_analysis.python import PythonAnalyzer


class TestPythonAnalyzer:
    """Test PythonAnalyzer."""

    @pytest.fixture
    def analyzer(self) -> PythonAnalyzer:
        """Create a PythonAnalyzer instance."""
        return PythonAnalyzer()

    def test_std_imports(self, analyzer: PythonAnalyzer, tmp_path: Path) -> None:
        """Test standard imports."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os\nimport sys")

        imports = analyzer.analyze_imports(file_path)
        assert "os" in imports
        assert "sys" in imports

    def test_from_imports(self, analyzer: PythonAnalyzer, tmp_path: Path) -> None:
        """Test from ... import ..."""
        file_path = tmp_path / "test.py"
        file_path.write_text("from pathlib import Path\nfrom typing import List, Dict")

        imports = analyzer.analyze_imports(file_path)
        assert "pathlib" in imports
        assert "typing" in imports

    def test_relative_imports(self, analyzer: PythonAnalyzer, tmp_path: Path) -> None:
        """Test relative imports."""
        # Relative imports depend on file location, here we test that they are captured
        # effectively as module names if possible, or usually `.`
        file_path = tmp_path / "test.py"
        file_path.write_text("from . import utils\nfrom ..core import config")

        imports = analyzer.analyze_imports(file_path)
        # ast usually resolves these as None module if level > 0, or we need to handle them
        # Implementation should ideally return ".utils" or similar representation
        assert ".utils" in imports
        assert "..core" in imports

    def test_import_as_alias(self, analyzer: PythonAnalyzer, tmp_path: Path) -> None:
        """Test import with alias."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import pandas as pd")

        imports = analyzer.analyze_imports(file_path)
        assert "pandas" in imports

    def test_syntax_error_handling(self, analyzer: PythonAnalyzer, tmp_path: Path) -> None:
        """Test handling of syntax errors."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os\nthis is syntax error")

        imports = analyzer.analyze_imports(file_path)
        assert imports == []

    def test_non_existent_file(self, analyzer: PythonAnalyzer) -> None:
        """Test handling of non-existent file."""
        import uuid

        file_path = Path(f"/tmp/nonexistent_{uuid.uuid4()}.py")
        imports = analyzer.analyze_imports(file_path)
        assert imports == []

    @patch("ast.parse")
    def test_generic_exception(
        self, mock_parse: MagicMock, analyzer: PythonAnalyzer, tmp_path: Path
    ) -> None:
        """Test handling of generic exception during parsing."""
        file_path = tmp_path / "test.py"
        file_path.write_text("import os")

        mock_parse.side_effect = Exception("Generic error")
        imports = analyzer.analyze_imports(file_path)
        assert imports == []
