"""Architect module for planning analysis."""

from dataclasses import dataclass, field
from pathlib import Path

from lantern_cli.static_analysis.dependency_graph import DependencyGraph


@dataclass
class Batch:
    """A batch of files to analyze together."""

    id: int
    files: list[str]
    hint: str = ""


@dataclass
class Phase:
    """A phase of analysis corresponding to a dependency layer."""

    id: int
    batches: list[Batch]
    learning_objectives: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """The complete analysis plan."""

    phases: list[Phase]
    confidence_score: float = 1.0
    dependencies_mermaid: str = ""

    def to_markdown(self) -> str:
        """Convert plan to markdown format."""
        md = ["# Lantern Analysis Plan\n"]
        md.append(f"Confidence Score: {self.confidence_score:.2f}\n")

        if self.dependencies_mermaid:
            md.append("## Dependency Graph\n")
            md.append("```mermaid")
            md.append(self.dependencies_mermaid)
            md.append("```\n")

        for phase in self.phases:
            md.append(f"## Phase {phase.id}")
            if phase.learning_objectives:
                md.append("\n### Learning Objectives")
                for obj in phase.learning_objectives:
                    md.append(f"- {obj}")

            md.append("\n### Execution Batches")
            for batch in phase.batches:
                files_str = ", ".join(batch.files)
                hint_suffix = f"\n  - *Hint: {batch.hint}*" if batch.hint else ""
                md.append(f"- [ ] Batch {batch.id}: `{files_str}`{hint_suffix}")
            md.append("")

        return "\n".join(md)


class Architect:
    """Architect agent responsible for planning analysis."""

    BATCH_SIZE = 3

    def __init__(self, root_path: Path, dependency_graph: DependencyGraph) -> None:
        """Initialize Architect.

        Args:
            root_path: Project root path.
            dependency_graph: Initialized dependency graph.
        """
        self.root_path = root_path
        self.dep_graph = dependency_graph

    def generate_plan(self) -> Plan:
        """Generate analysis plan based on dependency graph."""
        layers = self.dep_graph.calculate_layers()
        phases = []

        # Group modules by layer index
        # layer_idx -> [module_names]
        layer_groups = {}
        for module, layer_idx in layers.items():
            if layer_idx not in layer_groups:
                layer_groups[layer_idx] = []
            layer_groups[layer_idx].append(module)

        # Sort layers by index (0 is bottom/independent)
        sorted_layer_idxs = sorted(layer_groups.keys())

        global_batch_id = 1

        for layer_idx in sorted_layer_idxs:
            files = sorted(layer_groups[layer_idx])
            batches = []

            # Chunk files into batches
            for i in range(0, len(files), self.BATCH_SIZE):
                batch_files = files[i : i + self.BATCH_SIZE]
                batches.append(Batch(id=global_batch_id, files=batch_files))
                global_batch_id += 1

            phase = Phase(
                id=layer_idx + 1 if layer_idx >= 0 else 0,  # Handle -1 for cycles
                batches=batches,
                learning_objectives=self._generate_learning_objectives(layer_idx, files),
            )
            phases.append(phase)

        return Plan(
            phases=phases,
            confidence_score=self.calculate_confidence(),
            dependencies_mermaid=self.generate_mermaid_graph(),
        )

    def calculate_confidence(self) -> float:
        """Calculate confidence score based on analysis completeness."""
        score = 1.0

        # Reduce score if cycles detected
        cycles = self.dep_graph.detect_cycles()
        if cycles:
            score -= 0.1 * len(cycles)

        return max(0.0, score)

    def generate_mermaid_graph(self) -> str:
        """Generate Mermaid diagram of the dependency graph."""
        lines = ["graph TD"]

        # Get all dependencies
        deps = self.dep_graph.dependencies

        # Filter strictly to avoid clutter if too large, but for now dump all
        # To make it readable, we might want to only show file names not full paths
        # Assuming module names are already relative/short

        has_edges = False
        for source, targets in deps.items():
            for target in targets:
                # Sanitize names for mermaid
                s_safe = source.replace(".", "_").replace("/", "_").replace("-", "_")
                t_safe = target.replace(".", "_").replace("/", "_").replace("-", "_")
                lines.append(f"    {s_safe}[{source}] --> {t_safe}[{target}]")
                has_edges = True

        if not has_edges:
            lines.append("    NoDependencies[No Dependencies Detected]")

        return "\n".join(lines)

    def _generate_learning_objectives(self, layer_idx: int, files: list[str]) -> list[str]:
        """Generate learning objectives for a phase."""
        # In a real implementation, this might use LLM or heuristics based on file names
        # For now, return generic objectives
        return [
            f"Understand the role of {len(files)} module(s) in Layer {layer_idx}",
            "Identify key data structures and interfaces",
        ]
