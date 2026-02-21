"""Tests for Architect module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lantern_cli.core.architect import Architect, Plan
from lantern_cli.static_analysis.dependency_graph import DependencyGraph


class TestArchitect:
    """Test Architect class."""

    @pytest.fixture
    def mock_dependency_graph(self) -> MagicMock:
        """Create a mock dependency graph."""
        graph = MagicMock(spec=DependencyGraph)
        # Mock some modules and layers
        # Layer 0: utils
        # Layer 1: core -> utils
        # Layer 2: api -> core
        graph.calculate_layers.return_value = {"utils.py": 0, "core.py": 1, "api.py": 2}
        graph.dependencies = {}
        return graph

    @pytest.fixture
    def architect(self, mock_dependency_graph: MagicMock) -> Architect:
        """Create an Architect instance."""
        return Architect(root_path=Path("/tmp"), dependency_graph=mock_dependency_graph)

    def test_generate_plan_structure(self, architect: Architect) -> None:
        """Test that generate_plan creates a valid Plan object."""
        plan = architect.generate_plan()

        assert isinstance(plan, Plan)
        assert len(plan.phases) == 3  # 3 layers -> 3 phases

        # Check Phase 1 (Layer 0)
        phase1 = plan.phases[0]
        assert phase1.id == 1
        assert "utils.py" in phase1.batches[0].files

        # Check Phase 2 (Layer 1)
        phase2 = plan.phases[1]
        assert phase2.id == 2
        assert "core.py" in phase2.batches[0].files

    def test_confidence_score(self, architect: Architect) -> None:
        """Test confidence score calculation."""
        # Mock graph to return circular dependencies
        architect.dep_graph.detect_cycles.return_value = [["a", "b", "a"]]

        score = architect.calculate_confidence()
        assert score < 1.0  # Should be lower due to cycles

        # Mock perfect graph
        architect.dep_graph.detect_cycles.return_value = []
        score_perfect = architect.calculate_confidence()
        assert score_perfect == 1.0

    def test_plan_markdown_generation(self, architect: Architect) -> None:
        """Test converting plan to markdown."""
        # Setup mock dependencies for mermaid
        architect.dep_graph.dependencies = {"a": {"b"}}

        plan = architect.generate_plan()
        md = plan.to_markdown()

        assert "# Lantern Analysis Plan" in md
        assert "## Phase 1" in md
        assert "- [ ] Batch 1" in md
        assert "Learning Objectives" in md
        assert "## Dependency Graph" in md
        assert "```mermaid" in md
        assert "a[a] --> b[b]" in md

    def test_batch_size_limit(self, mock_dependency_graph: MagicMock) -> None:
        """Test that batches respect the size limit (e.g., 3 files)."""
        # Mock a layer with many files
        files = {f"file{i}.py": 0 for i in range(10)}
        mock_dependency_graph.calculate_layers.return_value = files

        architect = Architect(Path("/tmp"), mock_dependency_graph)
        plan = architect.generate_plan()

        phase1 = plan.phases[0]
        # 10 files, batch size 3 -> 4 batches (3, 3, 3, 1)
        assert len(phase1.batches) == 4
        assert len(phase1.batches[0].files) == 3
        assert len(phase1.batches[3].files) == 1
