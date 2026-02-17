"""
Enhanced Context Management for Cross-Batch Analysis (Phase 4).

Replaces the compressed summary approach with structured analysis results,
enabling selective context retrieval based on file dependencies.

Key improvements:
- No information loss (structured storage instead of compression)
- Intelligent context selection based on file dependencies
- Dynamic context generation for each batch
- Support for querying previous analysis results
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class StructuredAnalysisResult(TypedDict):
    """
    Structured analysis result for a single file.

    Replaces the old compressed summary approach with detailed,
    queryable analysis information.
    """

    file_path: str
    summary: str  # File-level summary
    key_concepts: list[str]  # Key concepts and patterns
    design_patterns: list[str]  # Design patterns found
    dependencies: list[str]  # Files this file depends on
    dependents: list[str]  # Files that depend on this file
    relationships: list[dict[str, Any]]  # Cross-file relationships
    quality_score: float  # Analysis quality (0.0-1.0)
    analysis_depth: str  # "shallow", "medium", "deep"
    timestamp: str  # When this was analyzed
    batch_id: int  # Which batch analyzed this file


@dataclass
class FileAnalysisMetadata:
    """Metadata about analyzed files for quick lookup."""

    file_path: str
    analyzed: bool = False
    batch_id: int | None = None
    quality_score: float = 0.0
    dependencies: list[str] = field(default_factory=list)


class EnhancedContextManager:
    """
    Intelligent context management for cross-batch analysis.

    Instead of compressing context to a fixed size, stores structured
    analysis results and selectively retrieves relevant context based
    on file dependencies.
    """

    def __init__(
        self,
        dependency_graph: dict[str, list[str]] | None = None,
        max_context_length: int = 6000,
    ):
        """
        Initialize the context manager.

        Args:
            dependency_graph: Graph of file dependencies {file -> [deps]}
            max_context_length: Maximum length of generated context
        """
        self.dependency_graph = dependency_graph or {}
        self.max_context_length = max_context_length

        # Storage for structured analysis results
        self.file_analyses: dict[str, StructuredAnalysisResult] = {}

        # Quick lookup metadata
        self.file_metadata: dict[str, FileAnalysisMetadata] = {}

        # Track analysis order
        self.analysis_order: list[str] = []

    def store_analysis(
        self,
        file_path: str,
        summary: str,
        key_concepts: list[str],
        batch_id: int,
        quality_score: float = 0.8,
        design_patterns: list[str] | None = None,
        relationships: list[dict[str, Any]] | None = None,
        analysis_depth: str = "medium",
    ) -> None:
        """
        Store structured analysis result for a file.

        Args:
            file_path: Path to analyzed file
            summary: Analysis summary
            key_concepts: List of key concepts
            batch_id: ID of batch that performed analysis
            quality_score: Quality of analysis (0-1)
            design_patterns: Design patterns found
            relationships: Cross-file relationships
            analysis_depth: Depth of analysis performed
        """
        from datetime import datetime

        # Get dependencies from graph
        dependencies = self.dependency_graph.get(file_path, [])

        result: StructuredAnalysisResult = {
            "file_path": file_path,
            "summary": summary,
            "key_concepts": key_concepts,
            "design_patterns": design_patterns or [],
            "dependencies": dependencies,
            "dependents": [],  # Will be filled by get_dependents
            "relationships": relationships or [],
            "quality_score": quality_score,
            "analysis_depth": analysis_depth,
            "timestamp": datetime.now().isoformat(),
            "batch_id": batch_id,
        }

        self.file_analyses[file_path] = result
        self.analysis_order.append(file_path)

        # Update metadata
        self.file_metadata[file_path] = FileAnalysisMetadata(
            file_path=file_path,
            analyzed=True,
            batch_id=batch_id,
            quality_score=quality_score,
            dependencies=dependencies,
        )

        logger.info(f"Stored analysis for {file_path} (quality: {quality_score:.2f})")

    def get_relevant_context(
        self,
        target_files: list[str],
        include_depth: int = 1,
        min_quality: float = 0.5,
    ) -> str:
        """
        Get relevant context for analyzing target files.

        Intelligently selects previous analyses based on:
        1. Direct dependencies of target files
        2. Transitive dependencies (up to include_depth)
        3. Quality score threshold

        Args:
            target_files: Files to be analyzed in current batch
            include_depth: How many levels of dependencies to include
            min_quality: Only include analyses with quality >= this

        Returns:
            Formatted context string (truncated to max_context_length)
        """
        # Find all relevant files
        relevant_files = self._find_relevant_files(target_files, include_depth, min_quality)

        if not relevant_files:
            logger.debug(f"No relevant previous analyses for {target_files}")
            return ""

        # Sort by dependency order (dependencies first)
        sorted_files = self._sort_by_dependency_order(relevant_files, target_files)

        # Build context string
        context_parts = []

        for file_path in sorted_files:
            if file_path in self.file_analyses:
                analysis = self.file_analyses[file_path]
                context_parts.append(self._format_analysis_for_context(file_path, analysis))

        # Combine and truncate
        full_context = "\n\n".join(context_parts)

        if len(full_context) > self.max_context_length:
            logger.info(f"Context truncated: {len(full_context)} → {self.max_context_length}")
            full_context = full_context[: self.max_context_length] + "\n... (truncated)"

        return full_context

    def _find_relevant_files(
        self,
        target_files: list[str],
        include_depth: int,
        min_quality: float,
    ) -> set[str]:
        """
        Find all files relevant to analyzing target files.

        Includes:
        - Direct dependencies
        - Transitive dependencies (up to include_depth)
        - Files with sufficient quality scores
        """
        relevant = set()

        def add_dependencies(files: list[str], depth: int) -> None:
            if depth <= 0:
                return

            for file_path in files:
                if file_path in relevant:
                    continue

                # Check if we have this analysis
                if file_path not in self.file_analyses:
                    continue

                # Check quality threshold
                analysis = self.file_analyses[file_path]
                if analysis["quality_score"] < min_quality:
                    continue

                relevant.add(file_path)

                # Recursively add dependencies
                deps = analysis["dependencies"]
                add_dependencies(deps, depth - 1)

        # Start with direct dependencies of target files
        for target_file in target_files:
            deps = self.dependency_graph.get(target_file, [])
            add_dependencies(deps, include_depth)

        return relevant

    def _sort_by_dependency_order(self, files: set[str], target_files: list[str]) -> list[str]:
        """
        Sort files by dependency order (dependencies first).

        Files with no unanalyzed dependencies come first.
        """
        sorted_files = []
        remaining = set(files)

        while remaining:
            # Find files with no dependencies in remaining set
            available = [
                f
                for f in remaining
                if not any(dep in remaining for dep in self.dependency_graph.get(f, []))
            ]

            if not available:
                # Circular dependency or all unanalyzed deps
                available = list(remaining)

            # Add by analysis order
            for f in self.analysis_order:
                if f in available:
                    sorted_files.append(f)
                    remaining.remove(f)
                    available.remove(f)

            # Add any remaining (shouldn't happen normally)
            sorted_files.extend(available)
            remaining -= set(available)

        return sorted_files

    def _format_analysis_for_context(
        self, file_path: str, analysis: StructuredAnalysisResult
    ) -> str:
        """
        Format a single analysis result for inclusion in context.
        """
        parts = [f"## {file_path}"]

        # Add summary
        if analysis["summary"]:
            parts.append(f"**Summary**: {analysis['summary'][:200]}")

        # Add key concepts
        if analysis["key_concepts"]:
            parts.append(f"**Concepts**: {', '.join(analysis['key_concepts'][:5])}")

        # Add design patterns
        if analysis["design_patterns"]:
            parts.append(f"**Patterns**: {', '.join(analysis['design_patterns'][:3])}")

        # Add quality info
        parts.append(
            f"(Quality: {analysis['quality_score']:.1f}, Depth: {analysis['analysis_depth']})"
        )

        return "\n".join(parts)

    def get_analysis(self, file_path: str) -> StructuredAnalysisResult | None:
        """Get stored analysis for a specific file."""
        return self.file_analyses.get(file_path)

    def get_all_analyses(self) -> dict[str, StructuredAnalysisResult]:
        """Get all stored analyses."""
        return self.file_analyses.copy()

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about stored analyses."""
        total_files = len(self.file_analyses)
        if total_files == 0:
            return {"total_files": 0, "avg_quality": 0.0}

        quality_scores = [analysis["quality_score"] for analysis in self.file_analyses.values()]
        avg_quality = sum(quality_scores) / len(quality_scores)

        depth_counts = {}
        for analysis in self.file_analyses.values():
            depth = analysis["analysis_depth"]
            depth_counts[depth] = depth_counts.get(depth, 0) + 1

        return {
            "total_files": total_files,
            "avg_quality": avg_quality,
            "analysis_depths": depth_counts,
            "batches_completed": max(
                (a["batch_id"] for a in self.file_analyses.values()), default=0
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize context manager state for checkpointing."""
        return {
            "file_analyses": self.file_analyses,
            "file_metadata": {k: asdict(v) for k, v in self.file_metadata.items()},
            "analysis_order": self.analysis_order,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        dependency_graph: dict[str, list[str]] | None = None,
        max_context_length: int = 6000,
    ) -> "EnhancedContextManager":
        """Deserialize context manager state from checkpoint."""
        manager = cls(dependency_graph, max_context_length)

        # Restore file analyses
        manager.file_analyses = data.get("file_analyses", {})

        # Restore metadata
        metadata_data = data.get("file_metadata", {})
        for file_path, meta_dict in metadata_data.items():
            manager.file_metadata[file_path] = FileAnalysisMetadata(**meta_dict)

        # Restore analysis order
        manager.analysis_order = data.get("analysis_order", [])

        return manager


def prepare_batch_context(
    context_manager: EnhancedContextManager,
    batch_files: list[str],
    dependency_graph: dict[str, list[str]],
    include_depth: int = 2,
    min_quality: float = 0.6,
) -> str:
    """
    Convenience function to prepare context for a batch.

    This replaces the old approach of keeping a global compressed summary.

    Args:
        context_manager: EnhancedContextManager instance
        batch_files: Files in current batch
        dependency_graph: Full dependency graph
        include_depth: Levels of dependencies to include
        min_quality: Minimum quality threshold

    Returns:
        Context string ready to include in batch prompt
    """
    # Ensure dependency graph is set
    if context_manager.dependency_graph != dependency_graph:
        context_manager.dependency_graph = dependency_graph

    # Get relevant context
    context = context_manager.get_relevant_context(batch_files, include_depth, min_quality)

    return context
