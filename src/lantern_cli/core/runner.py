"""Runner module for executing analysis batches.

Architecture:
- Uses Backend protocol (no direct LangChain dependency)
- Records actual token usage via LLMResponse.usage_metadata
- Extracts and validates response content
- Delegates compression to MemoryManager
- Supports both structured (LangChain) and agent-based (CLI) workflows
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lantern_cli.core.architect import Batch
from lantern_cli.core.state_manager import StateManager
from lantern_cli.llm.structured import (
    BatchInteraction,
    StructuredAnalysisOutput,
    StructuredAnalyzer,
)
from lantern_cli.utils.cost_tracker import CostTracker
from lantern_cli.utils.llm_logger import LLMLogger

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)


class Runner:
    """Orchestrates the analysis execution."""

    MAX_CONTEXT_LENGTH = 4000

    def __init__(
        self,
        root_path: Path,
        backend: "Backend",
        state_manager: StateManager,
        language: str = "en",
        model_name: str = "gemini-1.5-flash",
        is_local: bool = False,
        output_dir: str | None = None,
    ) -> None:
        """Initialize Runner.

        Args:
            root_path: Project root path.
            backend: Backend instance (from factory).
            state_manager: State manager instance.
            language: Output language (default: en).
            model_name: LLM model name for cost tracking.
            is_local: Whether the model is running locally (free).
        """
        self.root_path = root_path
        self.backend = backend
        self.state_manager = state_manager
        self.language = language
        # Base output dir from lantern.toml or CLI. Default: ".lantern"
        base_out = output_dir or ".lantern"
        self.base_output_dir = root_path / base_out
        self.sense_dir = self.base_output_dir / "sense"
        # Bottom-up / top-down outputs are placed under {base_output_dir}/output/{lang}/...
        self.cost_tracker = CostTracker(model_name, is_local=is_local)
        self.llm_logger = LLMLogger(root_path, output_dir=base_out)

    def run_batch(
        self,
        batch: Batch,
        prompt: str,
        on_file_progress: Callable[[str, str], None] | None = None,
    ) -> bool:
        """Execute a single batch analysis.

        Args:
            batch: Batch to analyze.
            prompt: Prompt to use.
            on_file_progress: Optional callback invoked with (file_path, status)
                where status is "start" or "done" for per-file progress tracking.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # 1. Prepare context (Temporal RAG)
            context = self._prepare_context()

            # 1a. Estimate cost for this batch
            est_result = self.cost_tracker.estimate_batch_cost(
                files=batch.files, context=context, prompt=prompt
            )

            if est_result:
                estimated_tokens, estimated_cost = est_result
                logger.debug(
                    f"Batch {batch.id}: Estimated {estimated_tokens} tokens, ${estimated_cost:.4f}"
                )
            else:
                logger.debug(
                    f"Batch {batch.id}: Cost estimation unavailable (offline/pricing error)"
                )

            # 2. Generate Bottom-up Markdown & save .sense file using StructuredAnalyzer
            # File reading is handled inside _generate_bottom_up_doc per-file
            sense_records = self._generate_bottom_up_doc(batch, on_file_progress)

            # 3. Update Global Summary from structured results
            # Collect summaries from all files in the batch
            batch_summary_lines = [f"Batch {batch.id} Analysis:"]
            for record in sense_records:
                analysis = record.get("analysis", {})
                if isinstance(analysis, dict):
                    summary = analysis.get("summary", "")
                    file_path = record.get("file_path", "unknown")
                    if summary:
                        batch_summary_lines.append(f"\n{file_path}: {summary}")

            new_content = "\n".join(batch_summary_lines)
            self.state_manager.update_global_summary(new_content)

            # 4. Update State
            self.state_manager.update_batch_status(batch.id, success=True)
            return True

        except Exception as e:
            logger.error(f"Failed to analyze batch {batch.id}: {e}")
            self.state_manager.update_batch_status(batch.id, success=False)
            return False

    def _extract_response_content(self, response: Any) -> str:
        """Extract and validate response content.

        Handles multiple response formats:
        - LLMResponse with .content attribute (str)
        - Legacy LangChain AIMessage with .content (string or list)
        - Raw string responses

        Args:
            response: Response object (LLMResponse, AIMessage, or string).

        Returns:
            Extracted and validated text content as non-empty string.

        Raises:
            ValueError: If response is None, content is empty, or extraction fails.
        """
        if not response:
            raise ValueError("Empty response from LLM")

        # Get content attribute, fallback to response itself if string
        content = getattr(response, "content", response)

        # Handle list responses (some LLMs return list of content)
        if isinstance(content, list):
            if not content:
                raise ValueError("Response content list is empty")
            content = "\n".join(str(item) for item in content if item)

        # Convert to string and strip
        text = str(content).strip()

        if not text:
            raise ValueError("Response content is empty after extraction")

        return text

    def _generate_bottom_up_doc(
        self,
        batch: Batch,
        on_file_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate formatted bottom-up documentation for the batch.

        Detects backend type and uses appropriate workflow:
        - CLIBackend: Agent-based file writing
        - Others: Structured JSON analysis

        Returns:
            List of sense records (dicts with batch, file_path, and analysis data).
        """
        # Import here to avoid circular dependency
        from lantern_cli.llm.backends.cli_backend import CLIBackend

        # Detect backend type and route to appropriate workflow
        if isinstance(self.backend, CLIBackend):
            logger.info(f"Using agent-based workflow for batch {batch.id}")
            return self._generate_bottom_up_doc_agent(batch, on_file_progress)
        else:
            logger.info(f"Using structured workflow for batch {batch.id}")
            return self._generate_bottom_up_doc_structured(batch, on_file_progress)

    def _generate_bottom_up_doc_structured(
        self,
        batch: Batch,
        on_file_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate bottom-up docs using structured JSON analysis (for LangChain backends).

        Primary path uses structured batch analysis (`chain.batch`) to generate
        per-file output in one request set. If batch call fails, it falls back
        to per-file invoke.

        Returns:
            List of sense records (dicts with batch, file_path, and analysis data).
        """
        # Output dir: {base_output_dir}/output/{lang}/bottom_up/...
        base_output_dir = self.base_output_dir / "output" / self.language / "bottom_up"

        analyzer = StructuredAnalyzer(self.backend)

        rel_paths: list[Path] = []
        batch_data: list[dict[str, str]] = []
        empty_indices: set[int] = set()
        for idx, file_path in enumerate(batch.files):
            rel_path, src_path = self._resolve_paths(file_path)
            rel_paths.append(rel_path)
            try:
                file_content = src_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error(f"Failed to read source file {src_path}: {exc}")
                file_content = ""
            if not file_content.strip():
                logger.info(f"Skipping empty file: {rel_path}")
                empty_indices.add(idx)
            batch_data.append({"file_content": file_content, "language": self.language})

        structured_results: list[StructuredAnalysisOutput | None] = [None] * len(batch.files)
        sense_records: list[dict[str, Any]] = []

        # Pre-fill stubs for empty files so they are never sent to the LLM.
        # summary="" is falsy, so _is_empty_record() filters these out of synthesis
        # regardless of the configured language.
        for idx in empty_indices:
            sense_records.append(
                {
                    "batch": batch.id,
                    "file_index": idx,
                    "file_path": batch.files[idx],
                    "prompt": batch_data[idx],
                    "raw_response": "empty file",
                    "status": "empty",
                    "analysis": {"summary": "", "key_insights": []},
                }
            )

        non_empty_pairs = [
            (i, batch_data[i]) for i in range(len(batch.files)) if i not in empty_indices
        ]
        interactions: list[BatchInteraction] = []
        if non_empty_pairs:
            try:
                interactions = analyzer.analyze_batch([d for _, d in non_empty_pairs])
            except Exception as exc:
                logger.error(f"Structured batch analysis failed: {exc}")

            for result_idx, (orig_idx, _) in enumerate(non_empty_pairs):
                if result_idx >= len(interactions):
                    break
                structured_results[orig_idx] = interactions[result_idx].analysis
                sense_records.append(
                    {
                        "batch": batch.id,
                        "file_index": orig_idx,
                        "file_path": batch.files[orig_idx],
                        **interactions[result_idx].to_dict(),
                    }
                )

            if any(
                structured_results[i] is None
                for i in range(len(batch.files))
                if i not in empty_indices
            ):
                for orig_idx, item_data in non_empty_pairs:
                    if structured_results[orig_idx] is not None:
                        continue
                    try:
                        single = analyzer.analyze(
                            file_content=item_data["file_content"],
                            language=self.language,
                        )
                        structured_results[orig_idx] = single
                        sense_records.append(
                            {
                                "batch": batch.id,
                                "file_index": orig_idx,
                                "file_path": batch.files[orig_idx],
                                "prompt": item_data,
                                "raw_response": "fallback invocation",
                                "analysis": single.model_dump(),
                            }
                        )
                    except Exception as exc:
                        logger.error(
                            f"Structured fallback invoke failed for "
                            f"{batch.files[orig_idx]}: {exc}"
                        )
                        sense_records.append(
                            {
                                "batch": batch.id,
                                "file_index": orig_idx,
                                "file_path": batch.files[orig_idx],
                                "prompt": item_data,
                                "raw_response": f"fallback error: {exc}",
                                "analysis": {
                                    "summary": "",
                                    "key_insights": [],
                                },
                            }
                        )

        num_files = len(batch.files)
        sense_path = self.sense_dir / f"batch_{batch.id:04d}.sense"
        try:
            sense_path.parent.mkdir(parents=True, exist_ok=True)
            with open(sense_path, "w", encoding="utf-8") as sense_f:
                json.dump(sense_records, sense_f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning(f"Unable to write sense metadata {sense_path}: {exc}")

        for idx, rel_path in enumerate(rel_paths):
            if on_file_progress:
                on_file_progress(batch.files[idx], "start")

            out_path = base_output_dir / rel_path.parent / f"{rel_path.name}.md"
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning(f"Could not create directory {out_path.parent}: {exc}")

            parsed = structured_results[idx]
            if idx in empty_indices:
                md_content = (
                    f"# {rel_path.name}\n\n"
                    f"> **Original File**: `{rel_path}`\n"
                    f"> **Batch**: {batch.id} ({idx + 1}/{num_files})\n\n"
                    f"## Summary\n\nEmpty file, no content to analyze.\n"
                )
            elif parsed is None:
                logger.warning(
                    f"No structured analysis for {rel_path}, skipping markdown generation"
                )
                md_content = (
                    f"# {rel_path.name}\n\n"
                    f"> **Original File**: `{rel_path}`\n"
                    f"> **Batch**: {batch.id} ({idx + 1}/{num_files})\n\n"
                    f"## Summary\n\nAnalysis failed or not available.\n"
                )
            else:
                md_content = self._render_structured_markdown(
                    rel_path=rel_path,
                    batch_id=batch.id,
                    index=idx + 1,
                    num_files=num_files,
                    parsed=parsed,
                )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            if on_file_progress:
                on_file_progress(batch.files[idx], "done")

        return sense_records

    def _resolve_paths(self, file_path: str) -> tuple[Path, Path]:
        path = Path(file_path)
        if path.is_absolute():
            src_path = path
            try:
                rel_path = path.relative_to(self.root_path)
            except ValueError:
                rel_path = Path(path.name)
            return rel_path, src_path
        return path, self.root_path / path

    def _render_structured_markdown(
        self,
        rel_path: Path,
        batch_id: int,
        index: int,
        num_files: int,
        parsed: StructuredAnalysisOutput,
    ) -> str:
        lines = [
            f"# {rel_path.name}",
            "",
            f"> **Original File**: `{rel_path}`",
            f"> **Batch**: {batch_id} ({index}/{num_files})",
            "",
            "## Summary",
            parsed.summary or "",
        ]
        if parsed.key_insights:
            lines.extend(["", "## Key Insights"])
            lines.extend([f"- {item}" for item in parsed.key_insights])
        if parsed.functions:
            lines.extend(["", "## Functions"])
            lines.extend([f"- {item}" for item in parsed.functions])
        if parsed.classes:
            lines.extend(["", "## Classes"])
            lines.extend([f"- {item}" for item in parsed.classes])
        if parsed.flow:
            lines.extend(["", "## Flow", parsed.flow])
        if parsed.flow_diagram:
            lines.extend(["", "```mermaid", parsed.flow_diagram, "```"])
        if parsed.references:
            lines.extend(["", "## References"])
            lines.extend([f"- {item}" for item in parsed.references])
        return "\n".join(lines).rstrip() + "\n"

    def _generate_bottom_up_doc_agent(
        self,
        batch: Batch,
        on_file_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate bottom-up docs using agent-based file writing (for CLI backends).

        The agent analyzes files and writes Markdown documentation directly
        using its file tool capabilities.

        Returns:
            List of sense records (metadata only, since files are written by agent).
        """
        from lantern_cli.llm.agent_analyzer import AgentAnalyzer

        # Output dir: {base_output_dir}/output/{lang}/bottom_up/...
        base_output_dir = self.base_output_dir / "output" / self.language / "bottom_up"

        analyzer = AgentAnalyzer(self.backend)

        # Prepare paths and data
        output_paths: list[Path] = []
        batch_data: list[dict[str, str]] = []
        source_files: list[str] = []
        sense_records: list[dict[str, Any]] = []

        for file_path in batch.files:
            if on_file_progress:
                on_file_progress(file_path, "start")

            rel_path, src_path = self._resolve_paths(file_path)

            # Output path for this file
            out_path = base_output_dir / rel_path.parent / f"{rel_path.name}.md"

            # Read file content
            try:
                file_content = src_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error(f"Failed to read source file {src_path}: {exc}")
                file_content = ""

            if not file_content.strip():
                logger.info(f"Skipping empty file: {rel_path}")
                try:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(
                        f"# {rel_path.name}\n\n"
                        f"> **Original File**: `{rel_path}`\n\n"
                        f"## Summary\n\nEmpty file, no content to analyze.\n",
                        encoding="utf-8",
                    )
                except OSError as exc:
                    logger.warning(f"Could not write stub for empty file {out_path}: {exc}")
                sense_records.append(
                    {
                        "batch": batch.id,
                        "file_path": file_path,
                        "prompt": {"file_content": "", "language": self.language},
                        "raw_response": "empty file",
                        "status": "empty",
                        "analysis": {"summary": "", "key_insights": []},
                    }
                )
                if on_file_progress:
                    on_file_progress(file_path, "done")
                continue

            output_paths.append(out_path)
            source_files.append(file_path)
            batch_data.append({"file_content": file_content, "language": self.language})

        # Let agent analyze and write non-empty files
        if batch_data:
            agent_records = analyzer.analyze_and_write_batch(
                items=batch_data,
                output_paths=output_paths,
                source_files=source_files,
                batch_id=batch.id,
                language=self.language,
            )
            sense_records.extend(agent_records)
            if on_file_progress:
                for sf in source_files:
                    on_file_progress(sf, "done")

        # Write sense metadata
        sense_path = self.sense_dir / f"batch_{batch.id:04d}.sense"
        try:
            sense_path.parent.mkdir(parents=True, exist_ok=True)
            with open(sense_path, "w", encoding="utf-8") as sense_f:
                json.dump(sense_records, sense_f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning(f"Unable to write sense metadata {sense_path}: {exc}")

        return sense_records

    def _prepare_context(self) -> str:
        """Prepare context from global summary."""
        summary = self.state_manager.state.global_summary
        if len(summary) > self.MAX_CONTEXT_LENGTH:
            return summary[: self.MAX_CONTEXT_LENGTH]  # Should be pre-truncated but safe guard
        return summary

    def get_cost_report(self) -> str:
        """Get cost report from cost tracker.

        Returns:
            Formatted cost report string.
        """
        return self.cost_tracker.get_report()
