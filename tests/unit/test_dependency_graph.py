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
