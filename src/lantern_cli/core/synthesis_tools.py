"""Data preparation utilities for agentic synthesis.

These functions transform raw .sense records into formatted context strings
suitable for LLM prompts. Each function is designed to extract a specific
aspect of the analysis data and format it concisely within a character budget.
"""

from typing import Any


def prepare_summaries(records: list[dict[str, Any]], max_chars: int = 8000) -> str:
    """Format all file summaries and key insights for LLM context.

    Args:
        records: Parsed .sense records (already filtered for empty).
        max_chars: Maximum output length in characters.

    Returns:
        Markdown-formatted summaries grouped by file path.
    """
    lines: list[str] = []
    for record in records:
        file_path = record.get("file_path", "unknown")
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            continue

        summary = analysis.get("summary", "")
        if not summary:
            continue

        lines.append(f"### {file_path}")
        lines.append(summary)
        for insight in analysis.get("key_insights", []):
            if insight:
                lines.append(f"- {insight}")
        lines.append("")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def prepare_file_details(records: list[dict[str, Any]], max_chars: int = 8000) -> str:
    """Format detailed file information including classes, functions, and flow.

    Args:
        records: Parsed .sense records.
        max_chars: Maximum output length in characters.

    Returns:
        Markdown-formatted file details.
    """
    lines: list[str] = []
    for record in records:
        file_path = record.get("file_path", "unknown")
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            continue

        summary = analysis.get("summary", "")
        if not summary:
            continue

        lines.append(f"### {file_path}")
        lines.append(summary)

        classes = analysis.get("classes", [])
        if classes:
            lines.append("**Classes**: " + ", ".join(c for c in classes if c))

        functions = analysis.get("functions", [])
        if functions:
            lines.append("**Functions**: " + ", ".join(f for f in functions if f))

        flow_diagram = analysis.get("flow_diagram", "")
        if flow_diagram:
            lines.append(f"\n```mermaid\n{flow_diagram}\n```")

        lines.append("")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def prepare_functions_summary(records: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """Format functions list from all files.

    Args:
        records: Parsed .sense records.
        max_chars: Maximum output length in characters.

    Returns:
        Markdown-formatted functions grouped by file.
    """
    lines: list[str] = []
    for record in records:
        file_path = record.get("file_path", "unknown")
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            continue
        functions = analysis.get("functions", [])
        if functions:
            lines.append(f"### {file_path}")
            for func in functions:
                if func:
                    lines.append(f"- {func}")
            lines.append("")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def prepare_classes_summary(records: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """Format classes list from all files.

    Args:
        records: Parsed .sense records.
        max_chars: Maximum output length in characters.

    Returns:
        Markdown-formatted classes grouped by file.
    """
    lines: list[str] = []
    for record in records:
        file_path = record.get("file_path", "unknown")
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            continue
        classes = analysis.get("classes", [])
        if classes:
            lines.append(f"### {file_path}")
            for cls in classes:
                if cls:
                    lines.append(f"- {cls}")
            lines.append("")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n...(truncated)"
    return result


def identify_entry_points(records: list[dict[str, Any]]) -> str:
    """Identify likely entry points from file analyses.

    Heuristic: files whose **filename** (not directory) contains common
    entry-point keywords, or whose functions include 'main'.

    Args:
        records: Parsed .sense records.

    Returns:
        Markdown-formatted entry point descriptions.
    """
    entry_keywords = ["main", "entry", "cli", "app", "server", "start", "__main__"]
    lines: list[str] = []

    for record in records:
        file_path = record.get("file_path", "unknown")
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            continue

        functions = analysis.get("functions", [])
        # Check only the filename, not directory components
        filename_lower = (
            file_path.rsplit("/", 1)[-1].lower() if "/" in file_path else file_path.lower()
        )

        is_entry = any(kw in filename_lower for kw in entry_keywords)
        has_main = any("main" in f.lower() for f in functions)

        if is_entry or has_main:
            lines.append(f"### {file_path}")
            summary = analysis.get("summary", "")
            if summary:
                lines.append(summary)
            for func in functions:
                if func:
                    lines.append(f"- {func}")
            lines.append("")

    return "\n".join(lines) if lines else "No clear entry points identified from file analysis."
