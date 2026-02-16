"""Memory management for Temporal RAG with intelligent compression."""
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages context memory with intelligent compression."""

    # Thresholds
    COMPRESS_THRESHOLD = 3000  # Compress when summary exceeds this length
    TARGET_LENGTH = 1000  # Target length after compression

    def __init__(self, backend: Optional["Backend"] = None) -> None:
        """Initialize MemoryManager.

        Args:
            backend: Backend instance for LLM compression (optional).
        """
        self.backend = backend
        self.compression_count = 0
        self.prompts = self._load_prompts()

    def update_summary(self, current_summary: str, new_content: str) -> str:
        """Update summary with new content, compressing if necessary.

        Args:
            current_summary: Existing summary.
            new_content: New content to append.

        Returns:
            Updated summary (compressed if needed).
        """
        # Append new content
        updated_summary = f"{current_summary}\n\n{new_content}".strip()

        # Check if compression needed
        if len(updated_summary) > self.COMPRESS_THRESHOLD:
            logger.info(
                f"Summary length ({len(updated_summary)}) exceeds threshold "
                f"({self.COMPRESS_THRESHOLD}). Compressing..."
            )
            compressed = self._compress_with_llm(updated_summary)
            if compressed:
                self.compression_count += 1
                logger.info(
                    f"Compression #{self.compression_count}: "
                    f"{len(updated_summary)} → {len(compressed)} chars"
                )
                return compressed
            else:
                # Fallback: simple truncation (keep tail)
                logger.warning("LLM compression failed. Using tail truncation fallback.")
                return "..." + updated_summary[-(self.COMPRESS_THRESHOLD - 3) :]

        return updated_summary

    def _load_prompts(self) -> dict:
        """Load prompts from JSON file.

        Returns:
            Dictionary containing prompt templates.
        """
        prompts_file = Path(__file__).parent.parent / "template" / "memory" / "prompts.json"

        if not prompts_file.exists():
            logger.warning(f"Prompts file not found at {prompts_file}")
            return {}

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load prompts from {prompts_file}: {e}")
            return {}

    def _compress_with_llm(self, long_summary: str) -> Optional[str]:
        """Compress summary using LLM backend.

        Args:
            long_summary: Long summary to compress.

        Returns:
            Compressed summary, or None if compression fails.
        """
        if not self.backend:
            logger.debug("No backend available for compression")
            return None

        try:
            # Get compression prompt template from JSON
            compression_config = self.prompts.get("compression", {})
            prompt_template = compression_config.get("template", "")

            if not prompt_template:
                logger.warning("No compression prompt template found in prompts.json")
                return None

            # Format prompt with parameters
            prompt = prompt_template.format(
                target_length=self.TARGET_LENGTH,
                long_summary=long_summary
            )

            response = self.backend.invoke(prompt)
            compressed = response.content
            compressed = str(compressed).strip()

            # Validate compression
            if len(compressed) < 100:
                logger.warning(f"Compressed summary too short ({len(compressed)} chars)")
                return None

            return compressed

        except Exception as e:
            logger.error(f"LLM compression failed: {e}")
            return None
