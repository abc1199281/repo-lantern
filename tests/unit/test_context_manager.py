"""
Tests for Enhanced Context Management (Phase 4).

Tests cover:
- Structured analysis result storage
- Dependency-aware context selection
- Context formatting and truncation
- Serialization/deserialization for checkpointing
"""

import pytest
from datetime import datetime

from lantern_cli.core.context_manager import (
    StructuredAnalysisResult,
    EnhancedContextManager,
    FileAnalysisMetadata,
    prepare_batch_context,
)


class TestStructuredAnalysisResult:
    """Test the structured analysis result type."""

    def test_can_create_analysis_result(self):
        """Test creating a structured analysis result."""
        result: StructuredAnalysisResult = {
            "file_path": "src/module.py",
            "summary": "Core module",
            "key_concepts": ["Factory", "Singleton"],
            "design_patterns": ["Factory Pattern"],
            "dependencies": ["src/base.py"],
            "dependents": [],
            "relationships": [],
            "quality_score": 0.85,
            "analysis_depth": "medium",
            "timestamp": datetime.now().isoformat(),
            "batch_id": 1,
        }

        assert result["file_path"] == "src/module.py"
        assert result["quality_score"] == 0.85
        assert "Factory" in result["key_concepts"]


class TestEnhancedContextManager:
    """Test the enhanced context manager."""

    @pytest.fixture
    def dependency_graph(self):
        """Create a sample dependency graph."""
        return {
            "src/main.py": ["src/module.py", "src/config.py"],
            "src/module.py": ["src/base.py"],
            "src/base.py": [],
            "src/config.py": [],
            "src/utils.py": ["src/base.py"],
        }

    @pytest.fixture
    def manager(self, dependency_graph):
        """Create a context manager with sample dependency graph."""
        return EnhancedContextManager(
            dependency_graph=dependency_graph, max_context_length=2000
        )

    def test_manager_initialization(self, manager, dependency_graph):
        """Test manager initializes correctly."""
        assert manager.dependency_graph == dependency_graph
        assert manager.max_context_length == 2000
        assert len(manager.file_analyses) == 0

    def test_store_analysis(self, manager):
        """Test storing an analysis result."""
        manager.store_analysis(
            file_path="src/base.py",
            summary="Base class with factory pattern",
            key_concepts=["Factory", "Abstract"],
            batch_id=1,
            quality_score=0.9,
            design_patterns=["Factory", "Template Method"],
        )

        assert "src/base.py" in manager.file_analyses
        assert manager.file_metadata["src/base.py"].analyzed is True
        assert manager.file_metadata["src/base.py"].quality_score == 0.9

    def test_store_multiple_analyses(self, manager):
        """Test storing multiple analyses."""
        files = ["src/base.py", "src/module.py", "src/config.py"]

        for i, file_path in enumerate(files):
            manager.store_analysis(
                file_path=file_path,
                summary=f"Summary for {file_path}",
                key_concepts=[f"Concept{j}" for j in range(2)],
                batch_id=i + 1,
                quality_score=0.8 + (i * 0.05),
            )

        assert len(manager.file_analyses) == 3
        assert len(manager.analysis_order) == 3

    def test_get_analysis(self, manager):
        """Test retrieving a stored analysis."""
        manager.store_analysis(
            file_path="src/base.py",
            summary="Test summary",
            key_concepts=["Test"],
            batch_id=1,
        )

        analysis = manager.get_analysis("src/base.py")

        assert analysis is not None
        assert analysis["file_path"] == "src/base.py"
        assert analysis["summary"] == "Test summary"

    def test_get_nonexistent_analysis(self, manager):
        """Test retrieving a nonexistent analysis."""
        analysis = manager.get_analysis("src/nonexistent.py")
        assert analysis is None

    def test_find_relevant_files_direct_dependencies(self, manager):
        """Test finding files based on direct dependencies."""
        # Store analyses for dependency chain
        manager.store_analysis(
            file_path="src/base.py",
            summary="Base",
            key_concepts=[],
            batch_id=1,
            quality_score=0.9,
        )
        manager.store_analysis(
            file_path="src/module.py",
            summary="Module",
            key_concepts=[],
            batch_id=1,
            quality_score=0.85,
        )

        # Find relevant files for src/main.py
        relevant = manager._find_relevant_files(
            target_files=["src/main.py"], include_depth=1, min_quality=0.5
        )

        # Should include src/module.py and src/config.py (direct deps)
        assert "src/module.py" in relevant
        # config.py has no stored analysis, so it won't be included
        assert len(relevant) >= 1

    def test_find_relevant_files_transitive_dependencies(self, manager):
        """Test finding files with transitive dependencies."""
        # Store full chain
        manager.store_analysis("src/base.py", "Base", [], 1, 0.9)
        manager.store_analysis("src/module.py", "Module", [], 1, 0.85)

        # Find with depth=2 (includes transitive deps)
        relevant = manager._find_relevant_files(
            target_files=["src/main.py"], include_depth=2, min_quality=0.5
        )

        # Should include both module and base
        assert "src/module.py" in relevant
        assert "src/base.py" in relevant

    def test_find_relevant_files_quality_filtering(self, manager):
        """Test that low-quality analyses are filtered out."""
        manager.store_analysis(
            "src/base.py", "Base", [], 1, quality_score=0.4  # Below threshold
        )
        manager.store_analysis(
            "src/module.py", "Module", [], 1, quality_score=0.85  # Above threshold
        )

        relevant = manager._find_relevant_files(
            target_files=["src/main.py"], include_depth=1, min_quality=0.5
        )

        # Only high-quality module should be included
        assert "src/module.py" in relevant
        assert "src/base.py" not in relevant

    def test_get_relevant_context(self, manager):
        """Test generating relevant context."""
        manager.store_analysis(
            file_path="src/base.py",
            summary="Core base class",
            key_concepts=["Factory", "Pattern"],
            batch_id=1,
        )
        manager.store_analysis(
            file_path="src/module.py",
            summary="Module using base",
            key_concepts=["Implementation"],
            batch_id=1,
        )

        context = manager.get_relevant_context(
            target_files=["src/main.py"], include_depth=2
        )

        # Context should contain information about dependencies
        assert len(context) > 0
        # Should mention at least one of the analyzed files
        assert ("src/base.py" in context or "src/module.py" in context)

    def test_context_truncation(self, manager):
        """Test that context is truncated to max length."""
        # Store many analyses with long summaries
        for i in range(5):
            manager.store_analysis(
                file_path=f"src/file{i}.py",
                summary="A" * 500,  # Long summary
                key_concepts=[f"Concept{j}" for j in range(10)],
                batch_id=1,
            )

        # Set very small max length to force truncation
        manager.max_context_length = 500

        # Update dependency graph to make all files relevant
        manager.dependency_graph = {
            "src/main.py": [f"src/file{i}.py" for i in range(5)],
            **{f"src/file{i}.py": [] for i in range(5)},
        }

        context = manager.get_relevant_context(
            target_files=["src/main.py"], include_depth=1
        )

        # Context should be truncated
        assert len(context) <= 600  # max + truncation marker
        assert "(truncated)" in context or len(context) <= 500

    def test_get_statistics(self, manager):
        """Test getting statistics."""
        manager.store_analysis("src/file1.py", "Summary1", [], 1, quality_score=0.8)
        manager.store_analysis("src/file2.py", "Summary2", [], 1, quality_score=0.9)

        stats = manager.get_statistics()

        assert stats["total_files"] == 2
        assert 0.8 <= stats["avg_quality"] <= 0.9
        assert stats["batches_completed"] >= 1

    def test_serialization_deserialization(self, manager):
        """Test serializing and deserializing context manager state."""
        # Store some analyses
        manager.store_analysis(
            "src/base.py", "Base class", ["Pattern1"], 1, quality_score=0.9
        )
        manager.store_analysis(
            "src/module.py", "Module", ["Pattern2"], 2, quality_score=0.85
        )

        # Serialize
        data = manager.to_dict()

        # Deserialize with same dependency graph
        restored = EnhancedContextManager.from_dict(
            data, dependency_graph=manager.dependency_graph
        )

        # Verify restored state
        assert len(restored.file_analyses) == 2
        assert "src/base.py" in restored.file_analyses
        assert restored.file_analyses["src/base.py"]["quality_score"] == 0.9
        assert restored.analysis_order == manager.analysis_order

    def test_empty_context_manager(self):
        """Test context manager with no stored analyses."""
        manager = EnhancedContextManager()

        context = manager.get_relevant_context(target_files=["src/main.py"])

        assert context == ""

    def test_prepare_batch_context_helper(self):
        """Test the prepare_batch_context convenience function."""
        dependency_graph = {
            "src/main.py": ["src/module.py"],
            "src/module.py": ["src/base.py"],
            "src/base.py": [],
        }

        manager = EnhancedContextManager(dependency_graph)
        manager.store_analysis("src/base.py", "Base", [], 1, 0.9)
        manager.store_analysis("src/module.py", "Module", [], 1, 0.85)

        context = prepare_batch_context(
            manager,
            batch_files=["src/main.py"],
            dependency_graph=dependency_graph,
            include_depth=2,
        )

        # Should generate non-empty context
        assert len(context) > 0

    def test_sort_by_dependency_order(self, manager):
        """Test sorting files by dependency order."""
        manager.store_analysis("src/base.py", "Base", [], 1)
        manager.store_analysis("src/module.py", "Module", [], 1)

        files = {"src/base.py", "src/module.py"}
        sorted_files = manager._sort_by_dependency_order(files, ["src/main.py"])

        # base.py should come before module.py (module depends on base)
        assert sorted_files.index("src/base.py") < sorted_files.index("src/module.py")

    def test_format_analysis_for_context(self, manager):
        """Test formatting analysis for context inclusion."""
        analysis: StructuredAnalysisResult = {
            "file_path": "src/module.py",
            "summary": "Test summary",
            "key_concepts": ["Concept1", "Concept2"],
            "design_patterns": ["Pattern1"],
            "dependencies": [],
            "dependents": [],
            "relationships": [],
            "quality_score": 0.85,
            "analysis_depth": "medium",
            "timestamp": datetime.now().isoformat(),
            "batch_id": 1,
        }

        formatted = manager._format_analysis_for_context("src/module.py", analysis)

        assert "src/module.py" in formatted
        assert "Test summary" in formatted
        assert "Concept1" in formatted
        assert "Pattern1" in formatted
        assert "0.9" in formatted or "0.8" in formatted  # Quality score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
