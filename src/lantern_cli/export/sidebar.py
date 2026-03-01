"""Sidebar generator for Docsify export."""

from pathlib import Path


def build_sidebar(export_dir: Path) -> str:
    """Build a Docsify _sidebar.md from the exported directory tree.

    Args:
        export_dir: Root directory of the exported site.

    Returns:
        Markdown string for _sidebar.md.
    """
    lines: list[str] = []

    # Top-level README (homepage)
    if (export_dir / "README.md").exists():
        lines.append("- [Home](/)")

    # Collect top-level markdown files (excluding README and _sidebar)
    top_files = sorted(
        f for f in export_dir.glob("*.md") if f.name not in ("README.md", "_sidebar.md")
    )
    for md_file in top_files:
        title = _title_from_filename(md_file.stem)
        lines.append(f"- [{title}](/{md_file.name})")

    # bottom_up/ subtree
    bottom_up = export_dir / "bottom_up"
    if bottom_up.is_dir():
        lines.append("- **Source Files**")
        _walk_tree(bottom_up, export_dir, lines, depth=1)

    return "\n".join(lines) + "\n"


def _walk_tree(directory: Path, root: Path, lines: list[str], depth: int) -> None:
    """Recursively walk a directory and append sidebar entries.

    Args:
        directory: Current directory to walk.
        root: Export root for computing relative paths.
        lines: Accumulator for sidebar lines.
        depth: Current indentation depth.
    """
    indent = "  " * depth
    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    for entry in entries:
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        rel = entry.relative_to(root)
        if entry.is_dir():
            title = _title_from_filename(entry.name)
            lines.append(f"{indent}- **{title}**")
            _walk_tree(entry, root, lines, depth + 1)
        elif entry.suffix == ".md":
            title = _title_from_filename(entry.stem)
            lines.append(f"{indent}- [{title}](/{rel.as_posix()})")


def _title_from_filename(stem: str) -> str:
    """Convert a filename stem to a human-readable title.

    Args:
        stem: Filename without extension.

    Returns:
        Title-cased string with underscores/hyphens replaced by spaces.
    """
    return stem.replace("_", " ").replace("-", " ").title()
