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
        model_name: str = "gemini-1.5-flash"
    ) -> None:
        """Initialize Runner.

        Args:
            root_path: Project root path.
            backend: Configured backend adapter.
            state_manager: State manager instance.
            language: Output language (default: en).
            model_name: LLM model name for cost tracking.
        """
        self.root_path = root_path
        self.backend = backend
        self.state_manager = state_manager
        self.language = language
        self.output_dir = root_path / ".lantern" / "sense"
        self.cost_tracker = CostTracker(model_name)

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
            estimated_tokens, estimated_cost = self.cost_tracker.estimate_batch_cost(
                files=batch.files,
                context=context,
                prompt=prompt
            )
            logger.debug(
                f"Batch {batch.id}: Estimated {estimated_tokens} tokens, ${estimated_cost:.4f}"
            )
            
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
            # Simple append strategy for MVP, or replace if summary is regenerative
            # For now, we append the new summary to the global context, 
            # effectively building a rolling summary.
            current_summary = self.state_manager.state.global_summary
            new_summary = f"{current_summary}\n\nBatch {batch.id} Summary:\n{result.summary}"
            
            # Truncate if too long (simple FIFO or smart truncation later)
            if len(new_summary) > self.MAX_CONTEXT_LENGTH:
                 # Keep the earliest part (overview) and the latest part (recent context)
                 # or just tail. Let's keep tail for now for simplicity.
                 new_summary = "..." + new_summary[-(self.MAX_CONTEXT_LENGTH-3):]

            self.state_manager.update_global_summary(new_summary)
            
            # 5. Update State
            self.state_manager.update_batch_status(batch.id, success=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze batch {batch.id}: {e}")
            self.state_manager.update_batch_status(batch.id, success=False)
            return False

    def _generate_bottom_up_doc(self, batch: Batch, result: AnalysisResult) -> None:
        """Generate formatted bottom-up documentation for the batch."""
        # Output dir: .lantern/output/{lang}/bottom_up/...
        base_output_dir = self.root_path / ".lantern" / "output" / self.language / "bottom_up"
        
        for file_path in batch.files:
            # 1. Determine output path
            # src/foo.py -> .lantern/output/en/bottom_up/src/foo.py.md
            rel_path = Path(file_path) # Assuming batch.files are relative to root or we treat them as such
            if rel_path.is_absolute():
                 try:
                     rel_path = rel_path.relative_to(self.root_path)
                 except ValueError:
                     # Fallback if not relative
                     rel_path = Path(rel_path.name)
            
            out_path = base_output_dir / rel_path.parent / f"{rel_path.name}.md"
            
            if not out_path.parent.exists():
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
            # 2. Generate Content
            # In a real batch with multiple files, the LLM result might be combined or specific.
            # For MVP, if batch size > 1, we might adhere to the "Single Analysis Result" mapping 
            # or expect the result to be split. 
            # *CRITICAL MVP SIMPLIFICATION*: We dump the WHOLE batch result into EACH file's doc 
            # or assume batch size = 1 for precise mapping.
            # Given Architect uses BATCH_SIZE=3, checking if result helps distinguish is hard without structured parsing per file.
            # Let's write a shared header for now.
            
            md_content = f"# {rel_path.name}\n\n"
            md_content += f"> **Original File**: `{rel_path}`\n\n"
            md_content += "## Summary\n"
            md_content += f"{result.summary}\n\n"
            md_content += "## Key Insights\n"
            for insight in result.key_insights:
                md_content += f"- {insight}\n"
            
            if result.questions:
                md_content += "\n## Questions\n"
                for q in result.questions:
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
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
        filename = f"batch_{batch.id:04d}.sense"
        file_path = self.output_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def get_cost_report(self) -> str:
        """Get cost report from cost tracker.

        Returns:
            Formatted cost report string.
        """
        return self.cost_tracker.get_report()
