"""Agentic Planner using LangGraph StateGraph for intelligent analysis planning.

Instead of the purely topological grouping in architect.py, this module uses a
multi-step LLM workflow to produce semantically meaningful file groupings with
per-batch analysis hints:

    analyze_structure → identify_patterns → semantic_grouping → generate_hints

Each node uses the LLM to progressively build understanding of the codebase,
resulting in:

1. Smarter file grouping (semantically related files analyzed together)
2. Per-batch hints that guide the analyzer to look for specific patterns
3. Better learning objectives derived from actual code understanding

Usage:
    from lantern_cli.core.agentic_planner import AgenticPlanner

    planner = AgenticPlanner(root_path, backend, language="en")
    plan = planner.generate_enhanced_plan(
        file_list, dependencies, reverse_dependencies, layers, mermaid_graph
    )
"""

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lantern_cli.core.architect import Batch, Phase, Plan
from lantern_cli.core.planning_tools import (
    prepare_dependency_summary,
    prepare_file_tree,
    prepare_layer_summary,
    sample_key_files,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "planning"

# Default batch size (matches Architect.BATCH_SIZE)
_DEFAULT_BATCH_SIZE = 3


def _load_prompts() -> dict[str, dict[str, str]]:
    """Load planning prompt templates from JSON."""
    path = TEMPLATE_DIR / "prompts.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_json_array(text: str) -> list[Any]:
    """Extract a JSON array from LLM output text.

    Handles common LLM formatting: markdown code blocks, preamble text, etc.

    Args:
        text: Raw LLM output that should contain a JSON array.

    Returns:
        Parsed JSON array.

    Raises:
        ValueError: If no valid JSON array can be extracted.
    """
    # Try to find JSON in code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Try direct parse
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try to find array in the text
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "[" and start is None:
            start = i
        if ch == "[" and start is not None:
            depth += 1
        elif ch == "]" and start is not None:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    pass

    raise ValueError(f"Could not extract JSON array from LLM output: {text[:200]}")


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from LLM output text.

    Args:
        text: Raw LLM output that should contain a JSON object.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    # Try to find JSON in code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try to find object in the text
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{" and start is None:
            start = i
        if ch == "{" and start is not None:
            depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    pass

    raise ValueError(f"Could not extract JSON object from LLM output: {text[:200]}")


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


class PlanningState(TypedDict):
    """Typed state flowing through the planning graph."""

    # Input data (set before graph invocation)
    file_tree: str
    dependency_summary: str
    layer_summary: str
    sampled_contents: str
    file_list_formatted: str
    language: str
    batch_size: int

    # LLM-generated intermediate analysis
    structure_analysis: str
    patterns_analysis: str

    # LLM-generated outputs
    semantic_groups_json: str
    batch_hints_json: str


# ---------------------------------------------------------------------------
# LLM invocation helper
# ---------------------------------------------------------------------------


def _invoke_backend(backend: Any, system: str, user: str) -> str:
    """Invoke the Backend with a combined system + user prompt.

    Args:
        backend: Backend instance (implements Backend protocol).
        system: System instruction content.
        user: User request content.

    Returns:
        Extracted text from the LLM response.

    Raises:
        RuntimeError: If the backend call fails.
    """
    prompt = f"[System]\n{system}\n\n[User]\n{user}"
    try:
        response = backend.invoke(prompt)
    except Exception as exc:
        raise RuntimeError(f"Backend invocation failed in planning: {exc}") from exc
    return response.content


# ---------------------------------------------------------------------------
# Graph node factories
# ---------------------------------------------------------------------------


def _make_analyze_structure(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the analyze_structure node."""

    def analyze_structure(state: PlanningState) -> dict[str, str]:
        lang = state["language"]
        cfg = prompts["analyze_structure"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                file_tree=state["file_tree"],
                dependency_summary=state["dependency_summary"],
                layer_summary=state["layer_summary"],
                sampled_contents=state["sampled_contents"],
            ),
        )
        return {"structure_analysis": result}

    return analyze_structure


def _make_identify_patterns(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the identify_patterns node."""

    def identify_patterns(state: PlanningState) -> dict[str, str]:
        lang = state["language"]
        cfg = prompts["identify_patterns"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                structure_analysis=state["structure_analysis"],
                sampled_contents=state["sampled_contents"],
                dependency_summary=state["dependency_summary"],
            ),
        )
        return {"patterns_analysis": result}

    return identify_patterns


def _make_semantic_grouping(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the semantic_grouping node."""

    def semantic_grouping(state: PlanningState) -> dict[str, str]:
        lang = state["language"]
        cfg = prompts["semantic_grouping"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                file_list_formatted=state["file_list_formatted"],
                patterns_analysis=state["patterns_analysis"],
                dependency_summary=state["dependency_summary"],
                layer_summary=state["layer_summary"],
                batch_size=state["batch_size"],
            ),
        )
        return {"semantic_groups_json": result}

    return semantic_grouping


def _make_generate_hints(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the generate_hints node."""

    def generate_hints(state: PlanningState) -> dict[str, str]:
        lang = state["language"]

        # Parse semantic groups to format batches for the prompt
        try:
            groups = _extract_json_array(state["semantic_groups_json"])
        except ValueError:
            groups = []

        batches_formatted_lines: list[str] = []
        for i, group in enumerate(groups):
            if isinstance(group, list):
                files_str = ", ".join(group)
                batches_formatted_lines.append(f"Batch {i}: {files_str}")

        batches_formatted = "\n".join(batches_formatted_lines)
        if not batches_formatted:
            batches_formatted = "No batches available."

        cfg = prompts["generate_hints"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                batches_formatted=batches_formatted,
                patterns_analysis=state["patterns_analysis"],
                structure_analysis=state["structure_analysis"],
            ),
        )
        return {"batch_hints_json": result}

    return generate_hints


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_planning_graph(backend: Any) -> Any:
    """Build and compile the planning StateGraph.

    Graph topology::

        START → analyze_structure → identify_patterns
              → semantic_grouping → generate_hints → END

    Args:
        backend: Backend instance (implements Backend protocol).

    Returns:
        Compiled LangGraph runnable.
    """
    prompts = _load_prompts()

    graph = StateGraph(PlanningState)

    graph.add_node("analyze_structure", _make_analyze_structure(backend, prompts))
    graph.add_node("identify_patterns", _make_identify_patterns(backend, prompts))
    graph.add_node("semantic_grouping", _make_semantic_grouping(backend, prompts))
    graph.add_node("generate_hints", _make_generate_hints(backend, prompts))

    graph.add_edge(START, "analyze_structure")
    graph.add_edge("analyze_structure", "identify_patterns")
    graph.add_edge("identify_patterns", "semantic_grouping")
    graph.add_edge("semantic_grouping", "generate_hints")
    graph.add_edge("generate_hints", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class AgenticPlanner:
    """LangGraph-based planner for intelligent analysis planning.

    Enhanced replacement for ``Architect`` when ``--planning-mode=agentic``.
    Uses LLM to semantically group files and generate per-batch analysis hints,
    producing higher quality analysis plans than pure topological sorting.
    """

    def __init__(
        self,
        root_path: Path,
        backend: Any,
        language: str = "en",
    ) -> None:
        """Initialize AgenticPlanner.

        Args:
            root_path: Project root path.
            backend: Backend instance (implements Backend protocol).
            language: Output language code (default: en).
        """
        self.root_path = root_path
        self.backend = backend
        self.language = language
        self.compiled_graph = build_planning_graph(backend)

    def generate_enhanced_plan(
        self,
        file_list: list[str],
        dependencies: dict[str, set[str]],
        reverse_dependencies: dict[str, set[str]],
        layers: dict[str, int],
        mermaid_graph: str = "",
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> Plan:
        """Generate an LLM-enhanced analysis plan.

        Takes the same static analysis data that Architect uses, but augments
        it with LLM-driven semantic grouping and per-batch hints.

        Args:
            file_list: List of all project files (relative paths).
            dependencies: Forward dependency map (source -> set of targets).
            reverse_dependencies: Reverse dependency map.
            layers: Layer assignments (file -> layer index).
            mermaid_graph: Mermaid diagram string for the dependency graph.
            batch_size: Maximum files per batch.

        Returns:
            Enhanced Plan with semantic grouping and batch hints.
        """
        if not file_list:
            logger.warning("No files provided to plan.")
            return Plan(phases=[], confidence_score=0.0, dependencies_mermaid=mermaid_graph)

        # Prepare input data for the graph
        file_tree = prepare_file_tree(file_list)
        dep_summary = prepare_dependency_summary(dependencies)
        layer_summary = prepare_layer_summary(layers)
        sampled = sample_key_files(file_list, dependencies, reverse_dependencies, self.root_path)
        file_list_formatted = "\n".join(f"- {f}" for f in sorted(file_list))

        initial_state: PlanningState = {
            "file_tree": file_tree,
            "dependency_summary": dep_summary,
            "layer_summary": layer_summary,
            "sampled_contents": sampled,
            "file_list_formatted": file_list_formatted,
            "language": self.language,
            "batch_size": batch_size,
            "structure_analysis": "",
            "patterns_analysis": "",
            "semantic_groups_json": "",
            "batch_hints_json": "",
        }

        logger.info("Starting agentic planning with LangGraph workflow...")
        result = self.compiled_graph.invoke(initial_state)
        logger.info("Agentic planning completed.")

        return self._build_plan(result, file_list, layers, mermaid_graph, batch_size)

    def _build_plan(
        self,
        result: dict[str, Any],
        file_list: list[str],
        layers: dict[str, int],
        mermaid_graph: str,
        batch_size: int,
    ) -> Plan:
        """Convert LLM graph output into a Plan object.

        Parses the semantic groups and batch hints from the LLM output.
        Falls back to layer-based grouping if parsing fails.

        Args:
            result: Graph execution result state.
            file_list: All project files.
            layers: Layer assignments.
            mermaid_graph: Mermaid diagram string.
            batch_size: Maximum files per batch.

        Returns:
            Plan object with semantic batches and hints.
        """
        # Parse semantic groups
        try:
            groups = _extract_json_array(result["semantic_groups_json"])
            # Validate: ensure all files are covered
            grouped_files = set()
            valid_groups: list[list[str]] = []
            for group in groups:
                if isinstance(group, list):
                    valid_files = [f for f in group if f in file_list]
                    if valid_files:
                        valid_groups.append(valid_files)
                        grouped_files.update(valid_files)

            # Add any missing files as extra groups
            missing = [f for f in file_list if f not in grouped_files]
            if missing:
                for i in range(0, len(missing), batch_size):
                    valid_groups.append(missing[i : i + batch_size])

            # Enforce batch_size: split large groups
            final_groups = _enforce_batch_size(valid_groups, batch_size)

        except (ValueError, TypeError) as exc:
            logger.warning(f"Failed to parse semantic groups, falling back to layers: {exc}")
            final_groups = _fallback_layer_groups(file_list, layers, batch_size)

        # Parse batch hints
        try:
            hints_raw = _extract_json_object(result["batch_hints_json"])
            hints: dict[int, str] = {int(k): str(v) for k, v in hints_raw.items()}
        except (ValueError, TypeError) as exc:
            logger.warning(f"Failed to parse batch hints: {exc}")
            hints = {}

        # Build Plan from groups
        phases: list[Phase] = []
        batch_id = 1

        # Organize groups into phases based on layer ordering
        # Compute average layer for each group to determine phase ordering
        group_layers: list[tuple[float, int]] = []
        for i, group in enumerate(final_groups):
            avg_layer = sum(layers.get(f, 0) for f in group) / max(len(group), 1)
            group_layers.append((avg_layer, i))
        group_layers.sort()

        # Group sequential batches with similar layer averages into phases
        current_phase_batches: list[Batch] = []
        current_phase_layer = -999.0
        phase_id = 1

        for avg_layer, group_idx in group_layers:
            group = final_groups[group_idx]
            hint = hints.get(group_idx, "")

            batch = Batch(id=batch_id, files=group, hint=hint)
            batch_id += 1

            # Start new phase if layer jumps significantly
            if avg_layer - current_phase_layer > 0.5 and current_phase_batches:
                phases.append(
                    Phase(
                        id=phase_id,
                        batches=current_phase_batches,
                        learning_objectives=self._generate_objectives(
                            current_phase_batches, result.get("patterns_analysis", "")
                        ),
                    )
                )
                phase_id += 1
                current_phase_batches = []

            current_phase_batches.append(batch)
            current_phase_layer = avg_layer

        # Flush remaining batches
        if current_phase_batches:
            phases.append(
                Phase(
                    id=phase_id,
                    batches=current_phase_batches,
                    learning_objectives=self._generate_objectives(
                        current_phase_batches, result.get("patterns_analysis", "")
                    ),
                )
            )

        # Calculate confidence based on parsing success
        confidence = 1.0
        if not hints:
            confidence -= 0.1
        if result.get("semantic_groups_json", "") == "":
            confidence -= 0.2

        return Plan(
            phases=phases,
            confidence_score=max(0.0, confidence),
            dependencies_mermaid=mermaid_graph,
        )

    @staticmethod
    def _generate_objectives(batches: list[Batch], patterns_analysis: str) -> list[str]:
        """Generate learning objectives for a phase from its batches.

        Uses batch hints and pattern analysis to create meaningful objectives.
        """
        objectives: list[str] = []
        all_files = [f for b in batches for f in b.files]
        objectives.append(f"Analyze {len(all_files)} file(s) in this phase")

        # Add hint-based objectives
        for batch in batches:
            if batch.hint:
                objectives.append(batch.hint)

        return objectives[:5]  # Cap at 5 objectives


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _enforce_batch_size(groups: list[list[str]], batch_size: int) -> list[list[str]]:
    """Split groups that exceed batch_size into smaller groups."""
    result: list[list[str]] = []
    for group in groups:
        if len(group) <= batch_size:
            result.append(group)
        else:
            for i in range(0, len(group), batch_size):
                result.append(group[i : i + batch_size])
    return result


def _fallback_layer_groups(
    file_list: list[str],
    layers: dict[str, int],
    batch_size: int,
) -> list[list[str]]:
    """Fall back to layer-based grouping (same as Architect)."""
    layer_groups: dict[int, list[str]] = {}
    for f in file_list:
        idx = layers.get(f, 0)
        if idx not in layer_groups:
            layer_groups[idx] = []
        layer_groups[idx].append(f)

    result: list[list[str]] = []
    for idx in sorted(layer_groups.keys()):
        files = sorted(layer_groups[idx])
        for i in range(0, len(files), batch_size):
            result.append(files[i : i + batch_size])
    return result
