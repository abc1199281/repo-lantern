"""Tests for TypeScript/JavaScript analyzer."""

from pathlib import Path

import pytest

from lantern_cli.static_analysis.typescript import TypeScriptAnalyzer


class TestTypeScriptAnalyzer:
    """Test TypeScriptAnalyzer."""

    @pytest.fixture
    def analyzer(self) -> TypeScriptAnalyzer:
        """Create a TypeScriptAnalyzer instance."""
        return TypeScriptAnalyzer()

    def test_es_module_default_import(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test ES module default import."""
        f = tmp_path / "app.ts"
        f.write_text("import React from 'react';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["react"]

    def test_es_module_named_import(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test ES module named import."""
        f = tmp_path / "app.ts"
        f.write_text("import { useState, useEffect } from 'react';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["react"]

    def test_es_module_side_effect_import(
        self, analyzer: TypeScriptAnalyzer, tmp_path: Path
    ) -> None:
        """Test ES module side-effect import."""
        f = tmp_path / "app.ts"
        f.write_text("import './styles.css';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["./styles.css"]

    def test_relative_import(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test relative imports."""
        f = tmp_path / "app.ts"
        f.write_text("import { helper } from './utils';\n" "import config from '../config';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["../config", "./utils"]

    def test_commonjs_require(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test CommonJS require."""
        f = tmp_path / "app.js"
        f.write_text("const fs = require('fs');\nconst utils = require('./utils');\n")
        result = analyzer.analyze_imports(f)
        assert result == ["./utils", "fs"]

    def test_re_export(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test re-exports."""
        f = tmp_path / "index.ts"
        f.write_text("export { default } from './component';\nexport * from './utils';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["./component", "./utils"]

    def test_type_import(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test TypeScript type imports."""
        f = tmp_path / "app.ts"
        f.write_text("import type { Config } from './config';\n")
        result = analyzer.analyze_imports(f)
        assert result == ["./config"]

    def test_mixed_imports(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test mixed import styles."""
        f = tmp_path / "app.ts"
        f.write_text(
            "import React from 'react';\n"
            "import { useState } from 'react';\n"
            "const path = require('path');\n"
            "import './global.css';\n"
            "export { helper } from './utils';\n"
        )
        result = analyzer.analyze_imports(f)
        assert result == ["./global.css", "./utils", "path", "react"]

    def test_empty_file(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test empty file."""
        f = tmp_path / "empty.ts"
        f.write_text("")
        result = analyzer.analyze_imports(f)
        assert result == []

    def test_no_imports(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test file with no imports."""
        f = tmp_path / "app.ts"
        f.write_text("const x = 42;\nconsole.log(x);\n")
        result = analyzer.analyze_imports(f)
        assert result == []

    def test_nonexistent_file(self, analyzer: TypeScriptAnalyzer) -> None:
        """Test nonexistent file."""
        result = analyzer.analyze_imports(Path("/nonexistent/file.ts"))
        assert result == []

    def test_syntax_errors_still_parse(self, analyzer: TypeScriptAnalyzer, tmp_path: Path) -> None:
        """Test that files with syntax errors still have imports extracted."""
        f = tmp_path / "broken.ts"
        f.write_text("import { foo } from './foo';\n" "const x = {{{;\n" "import bar from 'bar';\n")
        result = analyzer.analyze_imports(f)
        assert "./foo" in result
        assert "bar" in result
