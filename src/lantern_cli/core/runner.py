"""Runner module for executing analysis batches.

Architecture:
- Directly uses LangChain ChatModel (no adapter layer)
- Records actual token usage via response.usage_metadata
- Extracts and validates response content
- Delegates compression to MemoryManager

LLM Response Contract:
- Must return object with .content attribute
- For cost tracking: optional .usage_metadata dict with 'input_tokens' and 'output_tokens'
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

from lantern_cli.core.architect import Batch
from lantern_cli.core.state_manager import StateManager
from lantern_cli.llm.structured import (
    BatchInteraction,
    StructuredAnalysisOutput,
    StructuredAnalyzer,
)
from lantern_cli.utils.cost_tracker import CostTracker
from lantern_cli.utils.llm_logger import LLMLogger, timed_invoke

logger = logging.getLogger(__name__)


class Runner:
    """Orchestrates the analysis execution."""

    MAX_CONTEXT_LENGTH = 4000

    def __init__(
        self, 
        root_path: Path, 
        llm: Any,
        state_manager: StateManager,
        language: str = "en",
        model_name: str = "gemini-1.5-flash",
        is_local: bool = False,
        output_dir: Optional[str] = None,
    ) -> None:
        """Initialize Runner.

        Args:
            root_path: Project root path.
            llm: LangChain ChatModel instance (from factory).
            state_manager: State manager instance.
            language: Output language (default: en).
            model_name: LLM model name for cost tracking.
            is_local: Whether the model is running locally (free).
        """
        self.root_path = root_path
        self.llm = llm
        self.state_manager = state_manager
        self.language = language
        # Base output dir is configurable (from lantern.toml or CLI). Default to ".lantern" if unset.
        base_out = output_dir or ".lantern"
        self.base_output_dir = root_path / base_out
        self.sense_dir = self.base_output_dir / "sense"
        # Bottom-up / top-down outputs are placed under {base_output_dir}/output/{lang}/...
        self.cost_tracker = CostTracker(model_name, is_local=is_local)
        self.llm_logger = LLMLogger(root_path, output_dir=base_out)

    def run_batch(self, batch: Batch, prompt: str) -> bool:
        """Execute a single batch analysis.

        Args:
            batch: Batch to analyze.
            prompt: Prompt to use.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # 1. Prepare context (Temporal RAG)
            context = self._prepare_context()

            # 1a. Read file contents for the LLM prompt
            file_sections = []
            for file_path in batch.files:
                src_path = (
                    Path(file_path)
                    if Path(file_path).is_absolute()
                    else self.root_path / file_path
                )
                try:
                    content = src_path.read_text(encoding="utf-8")
                    file_sections.append(f"### {file_path}\n```\n{content}\n```")
                except OSError:
                    file_sections.append(f"### {file_path}\n(unable to read)")
            files_content = "\n\n".join(file_sections)
            
            # 1b. Estimate cost for this batch
            est_result = self.cost_tracker.estimate_batch_cost(
                files=batch.files,
                context=context,
                prompt=prompt
            )
            
            if est_result:
                estimated_tokens, estimated_cost = est_result
                logger.debug(
                    f"Batch {batch.id}: Estimated {estimated_tokens} tokens, ${estimated_cost:.4f}"
                )
            else:
                logger.debug(f"Batch {batch.id}: Cost estimation unavailable (offline/pricing error)")
            
            # 2. Call LLM directly (aggregate batch summary)
            full_prompt = f"{prompt}\n\nFiles:\n{files_content}"
            if context:
                full_prompt += f"\n\nContext:\n{context}"
            response, latency_ms = timed_invoke(self.llm, full_prompt)
            
            # 2b. Record actual usage from LangChain response
            self.cost_tracker.record_from_usage_metadata(response)
            
            # Extract and validate content from response
            try:
                raw_output = self._extract_response_content(response)
            except ValueError as e:
                logger.error(f"Failed to extract response content: {e}")
                raise
            
            logger.info(f"Batch {batch.id} completed with {len(raw_output)} chars")

            # 2c. Log LLM interaction
            self.llm_logger.log(
                caller="runner.run_batch",
                prompt=full_prompt,
                response=raw_output,
                response_obj=response,
                latency_ms=latency_ms,
            )
        
            # 3. Generate Bottom-up Markdown & save .sense file
            self._generate_bottom_up_doc(batch, raw_output)
            
            # 4. Update Global Summary
            # Delegate to StateManager which uses MemoryManager for compression
            new_content = f"Batch {batch.id} Summary:\n{raw_output}"
            self.state_manager.update_global_summary(new_content)
            
            # 5. Update State
            self.state_manager.update_batch_status(batch.id, success=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze batch {batch.id}: {e}")
            self.state_manager.update_batch_status(batch.id, success=False)
            return False

    def _extract_response_content(self, response: Any) -> str:
        """Extract and validate response content from LangChain ChatModel.
        
        Defensive extraction that handles multiple response formats:
        - AIMessage with .content attribute (string or list)
        - Raw string responses
        - List responses (some LLMs return list of content blocks)
        
        Validates at multiple levels:
        1. Response object is not None/falsy
        2. Content list is not empty (if list)
        3. Final string is not empty after stripping
        
        This method ensures run_batch() never crashes on unexpected response formats.

        Args:
            response: LangChain response object (AIMessage, ChatMessage, or string).

        Returns:
            Extracted and validated text content as non-empty string.

        Raises:
            ValueError: If response is None, content is empty, or extraction fails.
            
        Example:
            >>> response = llm.invoke([...])
            >>> text = runner._extract_response_content(response)
            >>> print(text)  # Guaranteed non-empty string
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

    def _generate_bottom_up_doc(self, batch: Batch, result: str) -> None:
        """Generate formatted bottom-up documentation for the batch.

        Primary path uses structured batch analysis (`chain.batch`) to generate
        per-file output in one request set. If batch call fails, it falls back
        to per-file invoke. If a file still fails, fallback to batch-level result.
        """
        # Output dir: {base_output_dir}/output/{lang}/bottom_up/...
        base_output_dir = self.base_output_dir / "output" / self.language / "bottom_up"

        analyzer = StructuredAnalyzer(self.llm)

        rel_paths: list[Path] = []
        batch_data: list[dict[str, str]] = []
        for file_path in batch.files:
            rel_path, src_path = self._resolve_paths(file_path)
            rel_paths.append(rel_path)
            try:
                file_content = src_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error(f"Failed to read source file {src_path}: {exc}")
                file_content = ""
            batch_data.append({"file_content": file_content, "language": self.language})

        structured_results: list[Optional[StructuredAnalysisOutput]] = [None] * len(batch.files)
        sense_records: list[dict[str, Any]] = []
        interactions: list[BatchInteraction] = []
        try:
            interactions = analyzer.analyze_batch(batch_data)
        except Exception as exc:
            logger.error(f"Structured batch analysis failed: {exc}")

        for idx, interaction in enumerate(interactions):
            if idx >= len(structured_results):
                break
            structured_results[idx] = interaction.analysis
            sense_records.append(
                {"batch": batch.id, "file_index": idx, "file_path": batch.files[idx], **interaction.to_dict()}
            )

        if any(item is None for item in structured_results):
            for idx, item in enumerate(structured_results):
                if item is not None:
                    continue
                try:
                    single = analyzer.analyze(
                        file_content=batch_data[idx]["file_content"],
                        language=self.language,
                    )
                    structured_results[idx] = single
                    sense_records.append(
                        {
                            "batch": batch.id,
                            "file_index": idx,
                            "file_path": batch.files[idx],
                            "prompt": batch_data[idx],
                            "raw_response": "fallback invocation",
                            "analysis": single.model_dump(),
                        }
                    )
                except Exception as exc:
                    logger.error(f"Structured fallback invoke failed for {batch.files[idx]}: {exc}")
                    sense_records.append(
                        {
                            "batch": batch.id,
                            "file_index": idx,
                            "file_path": batch.files[idx],
                            "prompt": batch_data[idx],
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
            out_path = base_output_dir / rel_path.parent / f"{rel_path.name}.md"
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning(f"Could not create directory {out_path.parent}: {exc}")

            parsed = structured_results[idx]
            if parsed is None:
                logger.warning(f"No structured analysis for {rel_path}, using batch-level fallback result")
                md_content = (
                    f"# {rel_path.name}\n\n"
                    f"> **Original File**: `{rel_path}`\n"
                    f"> **Batch**: {batch.id} ({idx + 1}/{num_files})\n\n"
                    f"## Summary\n\n{result}\n"
                )
            else:
                md_content = self._render_structured_markdown(
                    rel_path=rel_path, batch_id=batch.id, index=idx + 1, num_files=num_files, parsed=parsed
                )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_content)

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
        if parsed.risks:
            lines.extend(["", "## Risks"])
            lines.extend([f"- {item}" for item in parsed.risks])
        if parsed.references:
            lines.extend(["", "## References"])
            lines.extend([f"- {item}" for item in parsed.references])
        return "\n".join(lines).rstrip() + "\n"


    def _prepare_context(self) -> str:
        """Prepare context from global summary."""
        summary = self.state_manager.state.global_summary
        if len(summary) > self.MAX_CONTEXT_LENGTH:
            return summary[:self.MAX_CONTEXT_LENGTH] # Should be pre-truncated but safe guard
        return summary

    def _save_sense_file(self, batch: Batch, content: str) -> None:
        """Save the raw analysis output to a .sense file."""
        try:
            self.sense_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create sense directory {self.sense_dir}: {e}")
            
        filename = f"batch_{batch.id:04d}.sense"
        file_path = self.sense_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def get_cost_report(self) -> str:
        """Get cost report from cost tracker.

        Returns:
            Formatted cost report string.
        """
        return self.cost_tracker.get_report()
