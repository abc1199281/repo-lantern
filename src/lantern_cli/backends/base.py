"""Base classes for LLM backend adapters."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """Result of a batch analysis."""

    summary: str
    key_insights: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    raw_output: str = ""  # Raw CLI/API output for debugging


class BackendAdapter(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    def analyze_batch(
        self,
        files: list[str],
        context: str,
        prompt: str,
    ) -> AnalysisResult:
        """Analyze a batch of files.

        Args:
            files: List of file paths to analyze.
            context: Context from previous batches (Temporal RAG).
            prompt: Specific instructions for this batch.

        Returns:
            AnalysisResult object containing summary and insights.
        """
        pass

    @abstractmethod
    def synthesize(
        self,
        sense_files: list[str],
        target_language: str,
    ) -> str:
        """Synthesize final documentation from sense files.

        Args:
            sense_files: List of .sense file paths.
            target_language: Target language code (e.g., 'en', 'zh-TW').

        Returns:
            Final markdown content.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the backend is available and configured correctly.

        Returns:
            True if available, False otherwise.
        """
        pass
