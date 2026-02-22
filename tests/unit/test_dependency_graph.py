"""Tests for Dependency Graph construction."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lantern_cli.config.models import FilterConfig
from lantern_cli.static_analysis.dependency_graph import DependencyGraph


class TestDependencyGraph:
    """Test DependencyGraph."""

    @pytest.fixture
    def graph(self) -> DependencyGraph:
        """Create a DependencyGraph instance."""
        FilterConfig()
        return DependencyGraph(root_path=Path("/tmp"), file_filter=MagicMock())

    def test_add_dependency(self, graph: DependencyGraph) -> None:
        """Test adding dependencies."""
        graph.add_dependency("A", "B")
        graph.add_dependency("A", "C")

        assert "B" in graph.dependencies["A"]
        assert "C" in graph.dependencies["A"]

    def test_topological_sort(self, graph: DependencyGraph) -> None:
        """Test topological sort (layer calculation)."""
        # A -> B -> C
        graph.add_dependency("A", "B")
        graph.add_dependency("B", "C")

        layers = graph.calculate_layers()
        # Expected: C (level 0), B (level 1), A (level 2)
        # Or simplistic level calculation:
        # C has 0 deps -> level 0
        # B has 1 dep (C) -> level 1
        # A has 1 dep (B) -> max(level(B)) + 1 = 2

        assert layers["C"] == 0
        assert layers["B"] == 1
        assert layers["A"] == 2

    def test_circular_dependency(self, graph: DependencyGraph) -> None:
        """Test circular dependency detection."""
        # A -> B -> A
        graph.add_dependency("A", "B")
        graph.add_dependency("B", "A")

        cycles = graph.detect_cycles()
        assert len(cycles) > 0
        # Check that [A, B, A] or [B, A, B] is in cycles
        found = False
        for cycle in cycles:
            if set(cycle) == {"A", "B"}:
                found = True
                break
        assert found

    def test_complex_graph_metrics(self, graph: DependencyGraph) -> None:
        """Test complex graph metrics."""
        # A -> B, C
        # B -> D
        # C -> D
        # D -> []
        graph.add_dependency("A", "B")
        graph.add_dependency("A", "C")
        graph.add_dependency("B", "D")
        graph.add_dependency("C", "D")

        layers = graph.calculate_layers()
        assert layers["D"] == 0
        assert layers["B"] == 1
        assert layers["C"] == 1
        assert layers["A"] == 2


class TestTypeScriptDependencyGraph:
    """Test DependencyGraph with TypeScript files."""

    def test_typescript_files_discovered(self, tmp_path: Path) -> None:
        """Test that .ts and .tsx files are discovered and indexed."""
        # Create TS files
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.ts").write_text("import { helper } from './utils';\n")
        (src / "utils.ts").write_text("export const helper = () => {};\n")
        (src / "component.tsx").write_text("import React from 'react';\n")

        mock_filter = MagicMock()
        mock_filter.walk.return_value = [
            src / "app.ts",
            src / "utils.ts",
            src / "component.tsx",
        ]

        graph = DependencyGraph(root_path=tmp_path, file_filter=mock_filter)
        graph.build()

        # app.ts should depend on utils.ts
        assert "src/utils.ts" in graph.dependencies["src/app.ts"]

    def test_typescript_relative_import_resolution(self, tmp_path: Path) -> None:
        """Test that relative imports are resolved correctly."""
        src = tmp_path / "src"
        components = src / "components"
        components.mkdir(parents=True)

        (src / "app.ts").write_text("import { Button } from './components/Button';\n")
        (components / "Button.tsx").write_text("export const Button = () => {};\n")

        mock_filter = MagicMock()
        mock_filter.walk.return_value = [
            src / "app.ts",
            components / "Button.tsx",
        ]

        graph = DependencyGraph(root_path=tmp_path, file_filter=mock_filter)
        graph.build()

        assert "src/components/Button.tsx" in graph.dependencies["src/app.ts"]

    def test_typescript_index_import(self, tmp_path: Path) -> None:
        """Test that directory imports resolve to index files."""
        src = tmp_path / "src"
        utils = src / "utils"
        utils.mkdir(parents=True)

        (src / "app.ts").write_text("import { helper } from './utils';\n")
        (utils / "index.ts").write_text("export const helper = () => {};\n")

        mock_filter = MagicMock()
        mock_filter.walk.return_value = [
            src / "app.ts",
            utils / "index.ts",
        ]

        graph = DependencyGraph(root_path=tmp_path, file_filter=mock_filter)
        graph.build()

        assert "src/utils/index.ts" in graph.dependencies["src/app.ts"]

    def test_typescript_js_files_supported(self, tmp_path: Path) -> None:
        """Test that .js and .jsx files are also handled."""
        (tmp_path / "app.js").write_text("const utils = require('./utils');\n")
        (tmp_path / "utils.js").write_text("module.exports = {};\n")

        mock_filter = MagicMock()
        mock_filter.walk.return_value = [
            tmp_path / "app.js",
            tmp_path / "utils.js",
        ]

        graph = DependencyGraph(root_path=tmp_path, file_filter=mock_filter)
        graph.build()

        assert "utils.js" in graph.dependencies["app.js"]

    def test_typescript_bare_imports_not_resolved(self, tmp_path: Path) -> None:
        """Test that bare module imports (e.g. 'react') don't create false edges."""
        (tmp_path / "app.ts").write_text("import React from 'react';\n")

        mock_filter = MagicMock()
        mock_filter.walk.return_value = [tmp_path / "app.ts"]

        graph = DependencyGraph(root_path=tmp_path, file_filter=mock_filter)
        graph.build()

        assert graph.dependencies["app.ts"] == set()
