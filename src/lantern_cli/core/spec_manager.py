"""Spec manager for associating specification documents with code modules.

Handles PDF/Markdown extraction, specs.toml persistence, file-to-spec matching,
and LLM-assisted auto-mapping.

Usage:
    from lantern_cli.core.spec_manager import load_specs, get_spec_context, add_spec

    entries = load_specs(lantern_dir)
    context = get_spec_context("src/auth/handler.py", entries, lantern_dir)
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)

SPEC_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "spec"

# Maximum characters of spec text before summarization is triggered
_SUMMARY_THRESHOLD = 6000

# Maximum characters of spec excerpt sent for auto-mapping
_AUTO_MAP_EXCERPT_LEN = 4000


@dataclass
class SpecEntry:
    """A single spec-to-module mapping entry."""

    path: str
    modules: list[str] = field(default_factory=list)
    summary_path: str = ""
    label: str = ""


def _load_spec_prompts() -> dict[str, dict[str, str]]:
    """Load spec prompt templates from JSON."""
    path = SPEC_TEMPLATE_DIR / "prompts.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_pdf(path: Path) -> str:
    """Extract text from a PDF file, converting tables to Markdown format.

    Args:
        path: Path to the PDF file.

    Returns:
        Extracted text with tables formatted as Markdown tables.
    """
    import pdfplumber

    sections: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                md_table = _table_to_markdown(table)
                text = text + "\n\n" + md_table
            sections.append(text)
    return "\n\n---\n\n".join(sections)


def extract_markdown(path: Path) -> str:
    """Read a Markdown file directly.

    Args:
        path: Path to the Markdown file.

    Returns:
        File contents as a string.
    """
    return path.read_text(encoding="utf-8")


def extract_spec(path: Path) -> str:
    """Extract text from a spec file based on its extension.

    Args:
        path: Path to the spec file (PDF or Markdown).

    Returns:
        Extracted text content.

    Raises:
        ValueError: If the file extension is not supported.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    elif suffix in (".md", ".markdown"):
        return extract_markdown(path)
    else:
        raise ValueError(f"Unsupported spec format: {suffix}. Use .pdf or .md files.")


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table to Markdown table format.

    Args:
        table: 2D list from pdfplumber (first row is header).

    Returns:
        Markdown-formatted table string.
    """
    if not table:
        return ""

    header = table[0]
    rows = table[1:]

    # Clean cells
    def clean(cell: str | None) -> str:
        if cell is None:
            return ""
        return str(cell).replace("\n", " ").strip()

    header_cells = [clean(c) for c in header]
    md_lines = [
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join("---" for _ in header_cells) + " |",
    ]
    for row in rows:
        cells = [clean(c) for c in row]
        # Pad if row has fewer columns than header
        while len(cells) < len(header_cells):
            cells.append("")
        md_lines.append("| " + " | ".join(cells[: len(header_cells)]) + " |")

    return "\n".join(md_lines)


# ---------------------------------------------------------------------------
# specs.toml persistence
# ---------------------------------------------------------------------------


def load_specs(lantern_dir: Path) -> list[SpecEntry]:
    """Load spec entries from .lantern/specs.toml.

    Args:
        lantern_dir: Path to the .lantern directory.

    Returns:
        List of SpecEntry objects. Empty list if file doesn't exist.
    """
    specs_path = lantern_dir / "specs.toml"
    if not specs_path.exists():
        return []

    with open(specs_path, "rb") as f:
        data = tomllib.load(f)

    entries: list[SpecEntry] = []
    for item in data.get("spec", []):
        entries.append(
            SpecEntry(
                path=item.get("path", ""),
                modules=item.get("modules", []),
                summary_path=item.get("summary_path", ""),
                label=item.get("label", ""),
            )
        )
    return entries


def save_specs(lantern_dir: Path, entries: list[SpecEntry]) -> None:
    """Save spec entries to .lantern/specs.toml.

    Args:
        lantern_dir: Path to the .lantern directory.
        entries: List of SpecEntry objects to save.
    """
    specs_path = lantern_dir / "specs.toml"
    specs_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Auto-generated by `lantern spec add`. Edit freely.\n"]
    for entry in entries:
        lines.append("[[spec]]")
        lines.append(f'path = "{entry.path}"')
        modules_str = ", ".join(f'"{m}"' for m in entry.modules)
        lines.append(f"modules = [{modules_str}]")
        if entry.summary_path:
            lines.append(f'summary_path = "{entry.summary_path}"')
        if entry.label:
            lines.append(f'label = "{entry.label}"')
        lines.append("")

    specs_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# File-to-spec matching
# ---------------------------------------------------------------------------


def get_spec_context(file_path: str, entries: list[SpecEntry], lantern_dir: Path) -> str:
    """Get concatenated spec summaries relevant to a given file.

    Uses glob pattern matching to find which specs apply to the file.

    Args:
        file_path: Relative file path to match against spec module patterns.
        entries: List of SpecEntry objects.
        lantern_dir: Path to the .lantern directory (for reading summaries).

    Returns:
        Formatted spec context string, or empty string if no specs match.
    """
    contexts: list[str] = []

    for entry in entries:
        if not entry.modules:
            continue

        spec = pathspec.PathSpec.from_lines("gitignore", entry.modules)
        if spec.match_file(file_path):
            summary = _read_summary(entry, lantern_dir)
            if summary:
                label = entry.label or Path(entry.path).stem
                contexts.append(f"[Specification: {label}]\n{summary}")

    if not contexts:
        return ""

    header = (
        "The following specification document(s) describe the design intent "
        "for this file. Use them to explain how the code implements the spec.\n\n"
    )
    return header + "\n\n---\n\n".join(contexts)


def get_all_spec_summaries(entries: list[SpecEntry], lantern_dir: Path) -> str:
    """Get concatenated summaries of all spec entries.

    Used for planning and synthesis phases where all specs are relevant.

    Args:
        entries: List of SpecEntry objects.
        lantern_dir: Path to the .lantern directory.

    Returns:
        Formatted string with all spec summaries, or empty string.
    """
    contexts: list[str] = []
    for entry in entries:
        summary = _read_summary(entry, lantern_dir)
        if summary:
            label = entry.label or Path(entry.path).stem
            modules_str = ", ".join(entry.modules)
            contexts.append(f"[Specification: {label}] (covers: {modules_str})\n{summary}")

    if not contexts:
        return ""

    header = (
        "The following specification documents describe the design intent "
        "for parts of this project:\n\n"
    )
    return header + "\n\n---\n\n".join(contexts)


def _read_summary(entry: SpecEntry, lantern_dir: Path) -> str:
    """Read the summary file for a spec entry, falling back to empty string."""
    if not entry.summary_path:
        return ""
    summary_path = lantern_dir / entry.summary_path
    if not summary_path.exists():
        return ""
    try:
        return summary_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# LLM-assisted operations
# ---------------------------------------------------------------------------


def auto_map_spec(
    backend: "Backend",
    spec_text: str,
    file_tree: str,
) -> list[str]:
    """Use LLM to determine which modules a spec document covers.

    Args:
        backend: Backend instance for LLM calls.
        spec_text: Extracted spec text (will be truncated to excerpt).
        file_tree: Repository file tree string.

    Returns:
        List of glob patterns matching the relevant modules.
    """
    prompts = _load_spec_prompts()
    cfg = prompts["auto_map"]

    excerpt = spec_text[:_AUTO_MAP_EXCERPT_LEN]
    if len(spec_text) > _AUTO_MAP_EXCERPT_LEN:
        excerpt += "\n\n... (truncated)"

    prompt = (
        f"[System]\n{cfg['system']}\n\n"
        f"[User]\n{cfg['user'].format(spec_excerpt=excerpt, file_tree=file_tree)}"
    )

    response = backend.invoke(prompt)
    return _parse_modules_response(response.content)


def summarize_spec(backend: "Backend", spec_text: str) -> str:
    """Use LLM to generate a concise summary of a spec document.

    Only called when spec text exceeds _SUMMARY_THRESHOLD.

    Args:
        backend: Backend instance for LLM calls.
        spec_text: Full extracted spec text.

    Returns:
        Concise summary string.
    """
    prompts = _load_spec_prompts()
    cfg = prompts["summarize"]

    prompt = f"[System]\n{cfg['system']}\n\n" f"[User]\n{cfg['user'].format(spec_text=spec_text)}"

    response = backend.invoke(prompt)
    return response.content.strip()


def _parse_modules_response(text: str) -> list[str]:
    """Parse LLM response for auto_map into a list of module glob patterns.

    Expected format: JSON object with "modules" key containing a list of strings.
    """
    text = text.strip()

    # Try to extract JSON from code blocks
    import re

    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "modules" in parsed:
            modules = parsed["modules"]
            if isinstance(modules, list):
                return [str(m) for m in modules if m]
        if isinstance(parsed, list):
            return [str(m) for m in parsed if m]
    except json.JSONDecodeError:
        pass

    logger.warning("Could not parse auto-map response, returning empty modules list")
    return []


# ---------------------------------------------------------------------------
# High-level operations (used by CLI)
# ---------------------------------------------------------------------------


def add_spec(
    lantern_dir: Path,
    spec_file: Path,
    backend: "Backend",
    file_tree: str,
) -> SpecEntry:
    """Add a spec file: copy, extract, auto-map, summarize, and save.

    Args:
        lantern_dir: Path to the .lantern directory.
        spec_file: Path to the source spec file.
        backend: Backend instance for LLM calls.
        file_tree: Repository file tree string.

    Returns:
        The created SpecEntry.
    """
    # 1. Copy to .lantern/specs/
    specs_dir = lantern_dir / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    dest = specs_dir / spec_file.name
    if not dest.exists() or dest.resolve() != spec_file.resolve():
        import shutil

        shutil.copy2(spec_file, dest)

    # 2. Extract text
    spec_text = extract_spec(dest)
    rel_path = f"specs/{spec_file.name}"

    # 3. Auto-map modules
    logger.info("Auto-mapping spec to modules...")
    modules = auto_map_spec(backend, spec_text, file_tree)

    # 4. Summarize (if large)
    summary_filename = f"specs/{spec_file.stem}.summary.md"
    summary_dest = lantern_dir / summary_filename
    if len(spec_text) > _SUMMARY_THRESHOLD:
        logger.info("Spec is large, generating summary...")
        summary = summarize_spec(backend, spec_text)
    else:
        summary = spec_text
    summary_dest.write_text(summary, encoding="utf-8")

    # 5. Create entry
    entry = SpecEntry(
        path=rel_path,
        modules=modules,
        summary_path=summary_filename,
        label=spec_file.stem,
    )

    # 6. Load existing entries, append, and save
    entries = load_specs(lantern_dir)
    # Replace if same path already exists
    entries = [e for e in entries if e.path != rel_path]
    entries.append(entry)
    save_specs(lantern_dir, entries)

    return entry


def build_file_tree(root_path: Path, file_list: list[str]) -> str:
    """Build a simple file tree string from a list of file paths.

    Args:
        root_path: Project root (unused, kept for API consistency).
        file_list: List of relative file paths.

    Returns:
        Formatted file tree string.
    """
    return "\n".join(f"- {f}" for f in sorted(file_list))
