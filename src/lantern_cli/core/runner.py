"""Runner module for executing analysis batches."""
import json
import logging
from pathlib import Path
from typing import Any, Optional

from lantern_cli.backends.base import BackendAdapter, AnalysisResult
from lantern_cli.core.architect import Batch
from lantern_cli.core.state_manager import StateManager
from lantern_cli.llm.structured import (
    BatchInteraction,
    StructuredAnalysisOutput,
    StructuredAnalyzer,
)
from lantern_cli.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class Runner:
    """Orchestrates the analysis execution."""

    MAX_CONTEXT_LENGTH = 4000

    def __init__(
        self, 
        root_path: Path, 
        backend: BackendAdapter, 
        state_manager: StateManager,
        language: str = "en",
        model_name: str = "gemini-1.5-flash",
        is_local: bool = False,
        output_dir: Optional[str] = None,
    ) -> None:
        """Initialize Runner.

        Args:
            root_path: Project root path.
            backend: Configured backend adapter.
            state_manager: State manager instance.
            language: Output language (default: en).
            model_name: LLM model name for cost tracking.
            is_local: Whether the model is running locally (free).
        """
        self.root_path = root_path
        self.backend = backend
        self.state_manager = state_manager
        self.language = language
        # Base output dir is configurable (from lantern.toml or CLI). Default to ".lantern" if unset.
        base_out = output_dir or ".lantern"
        self.base_output_dir = root_path / base_out
        self.sense_dir = self.base_output_dir / "sense"
        # Bottom-up / top-down outputs are placed under {base_output_dir}/output/{lang}/...
        self.cost_tracker = CostTracker(model_name, is_local=is_local)

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
            
            # 2. Call backend (aggregate batch summary)
            result = self.backend.summarize_batch(
                files=batch.files,
                context=context,
                prompt=prompt
            )
            
            # 2b. Record actual usage
            # For now, use estimated tokens as we don't have actual token counts from backends
            # In future, backends should return actual token counts
            input_tokens = self.cost_tracker.estimate_tokens(context + prompt)
            for file_path in batch.files:
                input_tokens += self.cost_tracker.estimate_file_tokens(file_path)
            output_tokens = self.cost_tracker.estimate_tokens(result.raw_output)
            
            self.cost_tracker.record_usage(input_tokens, output_tokens)
            logger.info(
                f"Batch {batch.id} completed: {input_tokens + output_tokens} tokens used"
            )
            
            # 3. Save .sense file
            self._save_sense_file(batch, result.raw_output)

            # 3b. Generate Bottom-up Markdown (Phase 5.5)
            self._generate_bottom_up_doc(batch, result)
            
            # 4. Update Global Summary
            # Delegate to StateManager which uses MemoryManager for compression
            new_content = f"Batch {batch.id} Summary:\n{result.summary}"
            self.state_manager.update_global_summary(new_content)
            
            # 5. Update State
            self.state_manager.update_batch_status(batch.id, success=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze batch {batch.id}: {e}")
            self.state_manager.update_batch_status(batch.id, success=False)
            return False

    def _generate_bottom_up_doc(self, batch: Batch, result: AnalysisResult) -> None:
        """Generate formatted bottom-up documentation for the batch.

        Primary path uses structured batch analysis (`chain.batch`) to generate
        per-file output in one request set. If batch call fails, it falls back
        to per-file invoke. If a file still fails, fallback to batch-level result.
        """
        # Output dir: {base_output_dir}/output/{lang}/bottom_up/...
        base_output_dir = self.base_output_dir / "output" / self.language / "bottom_up"

        llm = self.backend.get_llm()
        analyzer = StructuredAnalyzer(llm)

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
                {"batch": batch.id, "file_index": idx, **interaction.to_dict()}
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
                            "prompt": batch_data[idx],
                            "raw_response": f"fallback error: {exc}",
                            "analysis": {
                                "summary": result.summary,
                                "key_insights": result.key_insights,
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
                md_content = self._render_fallback_markdown(
                    rel_path=rel_path, batch_id=batch.id, index=idx + 1, num_files=num_files, result=result
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
        if parsed.risks:
            lines.extend(["", "## Risks"])
            lines.extend([f"- {item}" for item in parsed.risks])
        if parsed.references:
            lines.extend(["", "## References"])
            lines.extend([f"- {item}" for item in parsed.references])
        return "\n".join(lines).rstrip() + "\n"

    def _render_fallback_markdown(
        self,
        rel_path: Path,
        batch_id: int,
        index: int,
        num_files: int,
        result: AnalysisResult,
    ) -> str:
        lines = [
            f"# {rel_path.name}",
            "",
            f"> **Original File**: `{rel_path}`",
            f"> **Batch**: {batch_id} ({index}/{num_files})",
            "",
            "## Summary",
            result.summary,
        ]
        if result.key_insights:
            lines.extend(["", "## Key Insights"])
            lines.extend([f"- {insight}" for insight in result.key_insights])
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
