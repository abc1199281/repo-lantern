"""Agentic Synthesizer using LangGraph StateGraph for intelligent documentation synthesis.

Instead of the rule-based text aggregation in synthesizer.py, this module uses a
multi-step LLM workflow:

    identify_patterns → cross_compare → generate_overview → generate_architecture
                                      → generate_getting_started → generate_concepts

Each node uses the LLM to produce progressively richer analysis, with later nodes
building on the output of earlier ones. This yields significantly better top-down
documentation because:

1. Pattern identification enables cross-file reasoning (design patterns, arch style)
2. Cross-comparison enables component relationship analysis
3. Each document is generated with full architectural context, not just per-file data

Usage:
    from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

    synth = AgenticSynthesizer(root_path, backend, language="en")
    synth.generate_top_down_docs()
"""

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lantern_cli.core.synthesis_tools import (
    identify_entry_points,
    prepare_classes_summary,
    prepare_file_details,
    prepare_functions_summary,
    prepare_summaries,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "synthesis"

# Patterns that indicate a record should be skipped (shared with synthesizer.py)
_SKIP_PATTERNS = ["未提供", "無法分析", "無法進行", "not provided", "unable to analyze"]

# Maximum LLM output per document before truncation
_MAX_DOC_LENGTH = 15000


def _load_prompts() -> dict[str, dict[str, str]]:
    """Load synthesis prompt templates from JSON."""
    path = TEMPLATE_DIR / "prompts.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


class SynthesisState(TypedDict):
    """Typed state flowing through the synthesis graph."""

    # Input data (set before graph invocation)
    sense_records: list[dict[str, Any]]
    plan_content: str
    dependency_mermaid: str
    language: str

    # LLM-generated intermediate analysis
    patterns_analysis: str
    cross_comparison: str

    # LLM-generated documents
    overview_doc: str
    architecture_doc: str
    getting_started_doc: str
    concepts_doc: str


# ---------------------------------------------------------------------------
# LLM invocation helper
# ---------------------------------------------------------------------------


def _invoke_backend(backend: Any, system: str, user: str) -> str:
    """Invoke the Backend with a combined system + user prompt.

    Combines the system and user messages into a single prompt string
    compatible with the Backend.invoke(str) protocol.

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
        raise RuntimeError(f"Backend invocation failed in synthesis: {exc}") from exc

    return response.content


# ---------------------------------------------------------------------------
# Graph node factories
# ---------------------------------------------------------------------------
# Each factory returns a node function closed over the LLM and prompts.
# Node functions accept the full state and return a partial dict to merge.


def _make_identify_patterns(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the identify_patterns node."""

    def identify_patterns(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        summaries = prepare_summaries(state["sense_records"])
        cfg = prompts["identify_patterns"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(summaries=summaries, language=lang),
        )
        return {"patterns_analysis": result}

    return identify_patterns


def _make_cross_compare(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the cross_compare node."""

    def cross_compare(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        summaries = prepare_summaries(state["sense_records"])
        cfg = prompts["cross_compare"]
        result = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                patterns_analysis=state["patterns_analysis"],
                summaries=summaries,
                language=lang,
            ),
        )
        return {"cross_comparison": result}

    return cross_compare


def _make_generate_overview(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the generate_overview node."""

    def generate_overview(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        summaries = prepare_summaries(state["sense_records"])
        cfg = prompts["generate_overview"]
        body = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                patterns_analysis=state["patterns_analysis"],
                cross_comparison=state["cross_comparison"],
                summaries=summaries,
                language=lang,
            ),
        )
        doc = "# Project Overview\n\n> Generated by Lantern (Agentic Synthesis)\n\n" + body
        return {"overview_doc": doc}

    return generate_overview


def _make_generate_architecture(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the generate_architecture node."""

    def generate_architecture(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        file_details = prepare_file_details(state["sense_records"])
        dep_mermaid = state.get("dependency_mermaid", "") or "No dependency graph available"
        cfg = prompts["generate_architecture"]
        body = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                patterns_analysis=state["patterns_analysis"],
                cross_comparison=state["cross_comparison"],
                dependency_mermaid=dep_mermaid,
                file_details=file_details,
                language=lang,
            ),
        )
        header = "# System Architecture\n\n> Generated by Lantern (Agentic Synthesis)\n\n"
        dep = state.get("dependency_mermaid", "")
        if dep:
            header += f"## Dependency Graph\n\n```mermaid\n{dep}\n```\n\n"
        doc = header + body
        return {"architecture_doc": doc}

    return generate_architecture


def _make_generate_getting_started(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the generate_getting_started node."""

    def generate_getting_started(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        functions_summary = prepare_functions_summary(state["sense_records"])
        entry_points = identify_entry_points(state["sense_records"])
        overview_summary = state.get("overview_doc", "")[:2000]
        cfg = prompts["generate_getting_started"]
        body = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                overview_summary=overview_summary,
                patterns_analysis=state["patterns_analysis"],
                functions_summary=functions_summary,
                entry_points=entry_points,
                language=lang,
            ),
        )
        doc = "# Getting Started\n\n> Generated by Lantern (Agentic Synthesis)\n\n" + body
        return {"getting_started_doc": doc}

    return generate_getting_started


def _make_generate_concepts(backend: Any, prompts: dict[str, dict[str, str]]) -> Any:
    """Create the generate_concepts node."""

    def generate_concepts(state: SynthesisState) -> dict[str, str]:
        lang = state["language"]
        classes_summary = prepare_classes_summary(state["sense_records"])
        cfg = prompts["generate_concepts"]
        body = _invoke_backend(
            backend,
            cfg["system"].format(language=lang),
            cfg["user"].format(
                patterns_analysis=state["patterns_analysis"],
                cross_comparison=state["cross_comparison"],
                classes_summary=classes_summary if classes_summary else "No classes found.",
                language=lang,
            ),
        )
        doc = "# Core Concepts\n\n> Generated by Lantern (Agentic Synthesis)\n\n" + body
        return {"concepts_doc": doc}

    return generate_concepts


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_synthesis_graph(backend: Any) -> Any:
    """Build and compile the synthesis StateGraph.

    Graph topology::

        START → identify_patterns → cross_compare → generate_overview
             → generate_architecture → generate_getting_started
             → generate_concepts → END

    Args:
        backend: Backend instance (implements Backend protocol).

    Returns:
        Compiled LangGraph runnable.
    """
    prompts = _load_prompts()

    graph = StateGraph(SynthesisState)

    graph.add_node("identify_patterns", _make_identify_patterns(backend, prompts))
    graph.add_node("cross_compare", _make_cross_compare(backend, prompts))
    graph.add_node("generate_overview", _make_generate_overview(backend, prompts))
    graph.add_node("generate_architecture", _make_generate_architecture(backend, prompts))
    graph.add_node("generate_getting_started", _make_generate_getting_started(backend, prompts))
    graph.add_node("generate_concepts", _make_generate_concepts(backend, prompts))

    graph.add_edge(START, "identify_patterns")
    graph.add_edge("identify_patterns", "cross_compare")
    graph.add_edge("cross_compare", "generate_overview")
    graph.add_edge("generate_overview", "generate_architecture")
    graph.add_edge("generate_architecture", "generate_getting_started")
    graph.add_edge("generate_getting_started", "generate_concepts")
    graph.add_edge("generate_concepts", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class AgenticSynthesizer:
    """LangGraph-based synthesizer for intelligent top-down documentation.

    Drop-in replacement for ``Synthesizer`` when ``--synthesis-mode=agentic``.
    Same public interface: ``generate_top_down_docs()`` reads .sense files and
    writes OVERVIEW.md, ARCHITECTURE.md, GETTING_STARTED.md, CONCEPTS.md.
    """

    def __init__(
        self,
        root_path: Path,
        backend: Any,
        language: str = "en",
        output_dir: str | None = None,
    ) -> None:
        """Initialize AgenticSynthesizer.

        Args:
            root_path: Project root path.
            backend: Backend instance (implements Backend protocol).
            language: Output language code (default: en).
            output_dir: Base output directory (default: .lantern).
        """
        self.root_path = root_path
        self.backend = backend
        self.language = language
        base_out = output_dir or ".lantern"
        self.base_output_dir = root_path / base_out
        self.sense_dir = self.base_output_dir / "sense"
        self.output_dir = self.base_output_dir / "output" / language / "top_down"
        self.compiled_graph = build_synthesis_graph(backend)

    # -- Data loading (mirrors Synthesizer for compatibility) ----------------

    def load_sense_files(self) -> list[dict[str, Any]]:
        """Load and parse all .sense files from the sense directory.

        Returns:
            List of parsed analysis records.
        """
        records: list[dict[str, Any]] = []
        if not self.sense_dir.exists():
            return records

        for sense_file in sorted(self.sense_dir.glob("*.sense")):
            try:
                with open(sense_file, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    records.extend(data)
                elif isinstance(data, dict):
                    records.append(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read {sense_file}: {e}")

        return records

    @staticmethod
    def _is_empty_record(record: dict[str, Any]) -> bool:
        """Check if a record represents an empty / unanalyzable file."""
        analysis = record.get("analysis", {})
        if not isinstance(analysis, dict):
            return True
        summary = analysis.get("summary", "")
        if not summary:
            return True
        summary_lower = summary.lower()
        return any(pat in summary_lower for pat in _SKIP_PATTERNS)

    def _load_mermaid_from_plan(self) -> str:
        """Extract the Mermaid content (without fences) from lantern_plan.md."""
        plan_path = self.base_output_dir / "lantern_plan.md"
        if not plan_path.exists():
            return ""
        try:
            text = plan_path.read_text(encoding="utf-8")
        except OSError:
            return ""
        match = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _load_plan_content(self) -> str:
        """Read the full lantern_plan.md content."""
        plan_path = self.base_output_dir / "lantern_plan.md"
        if not plan_path.exists():
            return ""
        try:
            return plan_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    # -- Main entry point ---------------------------------------------------

    def generate_top_down_docs(self) -> None:
        """Generate top-down documentation using the LangGraph workflow.

        Loads .sense files, runs the multi-step synthesis graph, and writes
        the four top-down documents to the output directory.
        """
        records = self.load_sense_files()
        if not records:
            logger.warning("No analysis results found to synthesize.")
            return

        records = [r for r in records if not self._is_empty_record(r)]
        if not records:
            logger.warning("All records are empty after filtering.")
            return

        # Build initial state
        initial_state: SynthesisState = {
            "sense_records": records,
            "plan_content": self._load_plan_content(),
            "dependency_mermaid": self._load_mermaid_from_plan(),
            "language": self.language,
            "patterns_analysis": "",
            "cross_comparison": "",
            "overview_doc": "",
            "architecture_doc": "",
            "getting_started_doc": "",
            "concepts_doc": "",
        }

        logger.info("Starting agentic synthesis with LangGraph workflow...")
        result = self.compiled_graph.invoke(initial_state)
        logger.info("Agentic synthesis completed.")

        # Write output files
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_doc("OVERVIEW.md", result["overview_doc"])
        self._write_doc("ARCHITECTURE.md", result["architecture_doc"])
        self._write_doc("GETTING_STARTED.md", result["getting_started_doc"])
        self._write_doc("CONCEPTS.md", result["concepts_doc"])

    def _write_doc(self, filename: str, content: str) -> None:
        """Write a document to the output directory, truncating if too long."""
        file_path = self.output_dir / filename
        if len(content) > _MAX_DOC_LENGTH:
            content = content[:_MAX_DOC_LENGTH] + "\n\n...(truncated)..."
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
