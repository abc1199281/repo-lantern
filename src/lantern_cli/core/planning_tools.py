"""Data preparation utilities for agentic planning.

These functions transform static analysis data (file lists, dependency graphs,
layers) into formatted context strings suitable for LLM prompts. They also
handle file sampling for the planner to understand the codebase.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def prepare_file_tree(file_list: list[str], max_chars: int = 4000) -> str:
    """Format a file list as an indented directory tree.

    Args:
        file_list: List of relative file paths.
        max_chars: Maximum output length in characters.

    Returns:
        Indented tree representation of the file structure.
    """
    if not file_list:
        return "No files found."

    # Build a tree structure from paths
    tree: dict[str, Any] = {}
    for file_path in sorted(file_list):
        parts = file_path.split("/")
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    # Render the tree
    lines: list[str] = []

    def _render(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> None:
        items = sorted(node.keys())
        for i, name in enumerate(items):
            last = i == len(items) - 1
            connector = "`-- " if last else "|-- "
            lines.append(f"{prefix}{connector}{name}")
            if node[name]:  # has children
                extension = "    " if last else "|   "
                _render(node[name], prefix + extension, last)

    _render(tree)
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def prepare_dependency_summary(
    dependencies: dict[str, set[str]], max_chars: int = 4000
) -> str:
    """Format dependency graph as readable text summary.

    Args:
        dependencies: Mapping of source file to set of target files.
        max_chars: Maximum output length in characters.

    Returns:
        Formatted dependency summary.
    """
    if not dependencies:
        return "No dependencies detected."

    lines: list[str] = []
    # Sort by number of dependencies (most connected first)
    sorted_deps = sorted(
        dependencies.items(), key=lambda x: len(x[1]), reverse=True
    )

    for source, targets in sorted_deps:
        if not targets:
            continue
        target_list = ", ".join(sorted(targets))
        lines.append(f"- {source} -> {target_list}")

    # Also summarize isolated files (no outgoing deps)
    isolated = [s for s, t in dependencies.items() if not t]
    if isolated:
        lines.append(f"\nIsolated files (no outgoing dependencies): {len(isolated)}")
        for f in sorted(isolated)[:10]:
            lines.append(f"  - {f}")
        if len(isolated) > 10:
            lines.append(f"  ... and {len(isolated) - 10} more")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def prepare_layer_summary(layers: dict[str, int], max_chars: int = 4000) -> str:
    """Format layer analysis as readable text.

    Args:
        layers: Mapping of file to layer index.
        max_chars: Maximum output length in characters.

    Returns:
        Formatted layer summary grouped by layer.
    """
    if not layers:
        return "No layer information available."

    # Group by layer
    layer_groups: dict[int, list[str]] = {}
    for file_path, layer_idx in layers.items():
        if layer_idx not in layer_groups:
            layer_groups[layer_idx] = []
        layer_groups[layer_idx].append(file_path)

    lines: list[str] = []
    for idx in sorted(layer_groups.keys()):
        files = sorted(layer_groups[idx])
        label = "Cycle" if idx == -1 else f"Layer {idx}"
        description = ""
        if idx == 0:
            description = " (leaf nodes, no outgoing dependencies)"
        elif idx == -1:
            description = " (circular dependencies detected)"
        lines.append(f"### {label}{description}")
        lines.append(f"{len(files)} file(s):")
        for f in files:
            lines.append(f"  - {f}")
        lines.append("")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def sample_key_files(
    file_list: list[str],
    dependencies: dict[str, set[str]],
    reverse_dependencies: dict[str, set[str]],
    root_path: Path,
    max_files: int = 8,
    max_lines_per_file: int = 60,
) -> str:
    """Sample key files from the project for LLM context.

    Selects important files based on heuristics:
    1. Files with the most dependents (most imported by others)
    2. Entry point files (main, cli, app, server)
    3. Configuration files

    Args:
        file_list: All project files.
        dependencies: Forward dependency map.
        reverse_dependencies: Reverse dependency map (target -> sources).
        root_path: Project root path for reading files.
        max_files: Maximum number of files to sample.
        max_lines_per_file: Maximum lines to read per file.

    Returns:
        Formatted sampled file contents.
    """
    if not file_list:
        return "No files available for sampling."

    # Score each file by importance
    entry_keywords = ["main", "entry", "cli", "app", "server", "start", "__main__"]
    config_keywords = ["config", "settings", "setup", "pyproject", "cargo"]
    interface_keywords = ["base", "abstract", "interface", "protocol", "types"]

    scored: list[tuple[float, str]] = []
    for file_path in file_list:
        score = 0.0
        filename = file_path.rsplit("/", 1)[-1].lower() if "/" in file_path else file_path.lower()

        # Dependents count (most imported = most important)
        dependents = len(reverse_dependencies.get(file_path, set()))
        score += dependents * 3.0

        # Entry point bonus
        if any(kw in filename for kw in entry_keywords):
            score += 5.0

        # Config file bonus
        if any(kw in filename for kw in config_keywords):
            score += 3.0

        # Interface/base class bonus
        if any(kw in filename for kw in interface_keywords):
            score += 4.0

        # __init__.py gets lower priority (usually boilerplate)
        if filename == "__init__.py":
            score -= 2.0

        scored.append((score, file_path))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [fp for _, fp in scored[:max_files]]

    # Read and format
    lines: list[str] = []
    for file_path in selected:
        full_path = root_path / file_path
        lines.append(f"### {file_path}")
        try:
            content = full_path.read_text(encoding="utf-8")
            file_lines = content.splitlines()
            if len(file_lines) > max_lines_per_file:
                sampled = "\n".join(file_lines[:max_lines_per_file])
                lines.append(f"```\n{sampled}\n... ({len(file_lines) - max_lines_per_file} more lines)\n```")
            else:
                lines.append(f"```\n{content}\n```")
        except OSError as exc:
            logger.warning(f"Could not read {full_path}: {exc}")
            lines.append("*(unable to read file)*")
        lines.append("")

    return "\n".join(lines)
