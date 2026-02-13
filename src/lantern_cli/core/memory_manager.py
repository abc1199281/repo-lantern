"""Memory management for Temporal RAG with intelligent compression."""
import logging
from typing import Optional

from lantern_cli.backends.base import BackendAdapter

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages context memory with intelligent compression."""

    # Thresholds
    COMPRESS_THRESHOLD = 3000  # Compress when summary exceeds this length
    TARGET_LENGTH = 1000  # Target length after compression

    def __init__(self, backend: Optional[BackendAdapter] = None) -> None:
        """Initialize MemoryManager.

        Args:
            backend: Backend adapter for LLM compression (optional).
        """
        self.backend = backend
        self.compression_count = 0

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

    def _compress_with_llm(self, long_summary: str) -> Optional[str]:
        """Compress summary using LLM.

        Args:
            long_summary: Long summary to compress.

        Returns:
            Compressed summary, or None if compression fails.
        """
        if not self.backend:
            logger.debug("No backend available for compression")
            return None

        try:
            # Compression prompt optimized for cheap models (Flash/Haiku)
            prompt = f"""Compress the following analysis summary to approximately {self.TARGET_LENGTH} characters while preserving:
1. Core architectural decisions and design patterns
2. Key module relationships and dependencies
3. Important technical details and constraints
4. Critical insights and findings

Remove redundant details and verbose explanations. Be concise but preserve technical accuracy.

SUMMARY TO COMPRESS:
{long_summary}

COMPRESSED SUMMARY (aim for ~{self.TARGET_LENGTH} chars):"""

            compressed = self.backend.invoke(prompt).strip()

            # Validate compression
            if len(compressed) < 100:
                logger.warning(f"Compressed summary too short ({len(compressed)} chars)")
                return None

            return compressed

        except Exception as e:
            logger.error(f"LLM compression failed: {e}")
            return None
