"""Runner module for executing analysis batches."""
import logging
from pathlib import Path
from typing import Optional

from lantern_cli.backends.base import BackendAdapter, AnalysisResult
from lantern_cli.core.architect import Batch
from lantern_cli.core.state_manager import StateManager
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
            
            # 2. Call backend
            result = self.backend.analyze_batch(
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
        
        Each file gets its own LLM analysis via backend.analyze_file() for
        unique per-file documentation.
        """
        # Output dir: {base_output_dir}/output/{lang}/bottom_up/...
        base_output_dir = self.base_output_dir / "output" / self.language / "bottom_up"
        
        context = self._prepare_context()
        
        for idx, file_path in enumerate(batch.files):
            # 1. Determine output path
            # src/foo.py -> .lantern/output/en/bottom_up/src/foo.py.md
            rel_path = Path(file_path)
            if rel_path.is_absolute():
                 try:
                     rel_path = rel_path.relative_to(self.root_path)
                 except ValueError:
                     rel_path = Path(rel_path.name)
            
            out_path = base_output_dir / rel_path.parent / f"{rel_path.name}.md"
            
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create directory {out_path.parent}: {e}")
            
            # 2. Per-file LLM analysis
            language_instruction = f" Please respond in {self.language}." if self.language != "en" else ""
            file_prompt = f"Analyze this file: {file_path}. Provide a summary, key insights, and questions.{language_instruction}"
            
            try:
                file_result = self.backend.analyze_file(
                    file=file_path,
                    context=context,
                    prompt=file_prompt,
                )
            except Exception as e:
                logger.error(f"Per-file analysis failed for {file_path}: {e}")
                # Fallback to batch-level result
                file_result = result
            
            # 3. Generate Content from per-file result
            num_files = len(batch.files)
            md_content = f"# {rel_path.name}\n\n"
            md_content += f"> **Original File**: `{rel_path}`\n"
            md_content += f"> **Batch**: {batch.id} ({idx + 1}/{num_files})\n\n"
            
            md_content += "## Summary\n"
            md_content += f"{file_result.summary}\n"
            
            if file_result.key_insights:
                md_content += "\n## Key Insights\n"
                for insight in file_result.key_insights:
                    md_content += f"- {insight}\n"
            
            if file_result.questions:
                md_content += "\n## Questions & TODOs\n"
                for q in file_result.questions:
                    md_content += f"- {q}\n"

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_content)



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
