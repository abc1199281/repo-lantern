"""Mermaid diagram syntax validator.

Provides ``clean_and_validate`` to strip fences, check structural validity,
and optionally run ``mmdc`` for strict syntax checking.

Flow:
    raw string (possibly fenced)
        -> strip_fences()
        -> structural_validate()  (always)
        -> mmdc_validate()        (only if mmdc is installed)
        -> return cleaned str | None
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Diagram type registry
# ---------------------------------------------------------------------------

# Maps recognised start tokens to their validation rules.
# Each entry: (pattern_to_match_header, requires_direction_check)
_DIAGRAM_TYPES: dict[str, bool] = {
    "graph": True,
    "flowchart": True,
    "sequenceDiagram": False,
    "classDiagram": False,
    "stateDiagram": False,
    "stateDiagram-v2": False,
    "erDiagram": False,
    "gantt": False,
    "pie": False,
    "mindmap": False,
    "timeline": False,
    "gitGraph": False,
    "journey": False,
    "xychart-beta": False,
    "block-beta": False,
}

_VALID_DIRECTIONS = frozenset({"TD", "TB", "LR", "RL", "BT"})

# Regex: leading whitespace + diagram keyword + optional colon/space
# Sort by length descending so "stateDiagram-v2" matches before "stateDiagram"
_HEADER_RE = re.compile(
    r"^\s*("
    + "|".join(re.escape(k) for k in sorted(_DIAGRAM_TYPES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_fences(raw: str) -> str:
    """Remove ```mermaid / ``` or plain ``` fences from raw text.

    Args:
        raw: Raw Mermaid string that may include markdown fences.

    Returns:
        Content with fences removed and surrounding whitespace stripped.
    """
    text = raw.strip()

    # Handle ```mermaid ... ``` or ``` ... ```
    fence_pattern = re.compile(
        r"^```(?:mermaid)?\s*\n?(.*?)\n?```\s*$",
        re.DOTALL | re.IGNORECASE,
    )
    match = fence_pattern.match(text)
    if match:
        return match.group(1).strip()

    # Handle opening fence with no closing fence (truncated LLM output)
    open_fence = re.compile(r"^```(?:mermaid)?\s*\n?(.*)", re.DOTALL | re.IGNORECASE)
    match = open_fence.match(text)
    if match:
        return match.group(1).rstrip("`").strip()

    return text


def _structural_validate(content: str) -> bool:
    """Run fast structural checks against the diagram content.

    Checks performed:
    1. Non-empty after stripping.
    2. First meaningful line matches a known diagram type keyword.
    3. For graph/flowchart: a valid direction specifier follows the keyword.
    4. At least one additional non-blank line exists after the header.

    Args:
        content: Cleaned Mermaid content (no fences).

    Returns:
        True if content passes all structural checks.
    """
    if not content.strip():
        logger.debug("Mermaid validation failed: empty content")
        return False

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        logger.debug("Mermaid validation failed: only whitespace lines")
        return False

    header = lines[0]
    match = _HEADER_RE.match(header)
    if not match:
        logger.debug(
            "Mermaid validation failed: unrecognised diagram type in header %r",
            header[:80],
        )
        return False

    keyword = match.group(1).lower()

    # Direction check for graph / flowchart
    requires_direction = _DIAGRAM_TYPES.get(keyword, False)
    if not requires_direction:
        # Check case-insensitive key
        for k, v in _DIAGRAM_TYPES.items():
            if k.lower() == keyword:
                requires_direction = v
                break

    if requires_direction:
        # Expect "graph TD" or "flowchart LR" style
        rest = header[match.end() :].strip()
        direction = rest.split()[0].upper() if rest else ""
        if direction not in _VALID_DIRECTIONS:
            logger.debug(
                "Mermaid validation failed: invalid direction %r (must be one of %s)",
                direction,
                _VALID_DIRECTIONS,
            )
            return False

    # Must have content after the header
    if len(lines) < 2:
        logger.debug("Mermaid validation failed: header only, no diagram body")
        return False

    return True


def _mmdc_available() -> bool:
    """Return True if the ``mmdc`` binary is on PATH."""
    return shutil.which("mmdc") is not None


def _mmdc_validate(content: str) -> bool:
    """Validate Mermaid syntax using the ``mmdc`` CLI tool.

    Writes content to a temp file, runs ``mmdc --input <file> --output /dev/null``
    and interprets the exit code.

    This function is a no-op (returns True) when mmdc is not installed,
    ensuring graceful degradation.

    Args:
        content: Cleaned Mermaid content to validate.

    Returns:
        True if mmdc accepts the syntax or is not installed; False if mmdc
        explicitly rejects the content.
    """
    if not _mmdc_available():
        return True

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mmd", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["mmdc", "--input", str(tmp_path), "--output", "/dev/null"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.debug(
                "mmdc rejected diagram: %s",
                (result.stderr or result.stdout)[:200],
            )
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("mmdc execution failed (graceful fallback): %s", exc)
        return True
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean_and_validate(raw: str) -> str | None:
    """Strip Mermaid fences, validate syntax, and return cleaned content.

    Performs two validation tiers:
    1. **Structural** (always): checks diagram type keyword, direction
       specifier for graph/flowchart, and non-empty body.
    2. **Strict** (optional): delegates to ``mmdc`` when it is installed.

    Args:
        raw: Raw Mermaid string from LLM output.  May include markdown
             code fences (```mermaid ... ```).

    Returns:
        Cleaned Mermaid string (no fences) if valid, or ``None`` if invalid.
        Returns ``None`` and logs a warning for invalid content.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None

    cleaned = _strip_fences(raw)

    if not _structural_validate(cleaned):
        logger.warning(
            "Invalid Mermaid diagram dropped (structural check failed). " "Preview: %r",
            cleaned[:120],
        )
        return None

    if not _mmdc_validate(cleaned):
        logger.warning(
            "Invalid Mermaid diagram dropped (mmdc strict check failed). " "Preview: %r",
            cleaned[:120],
        )
        return None

    return cleaned
