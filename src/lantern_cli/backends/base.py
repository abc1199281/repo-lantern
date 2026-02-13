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

    def analyze_file(
        self,
        file: str,
        context: str,
        prompt: str,
    ) -> AnalysisResult:
        """Analyze a single file.

        Default implementation delegates to analyze_batch with a single file.
        Subclasses can override for optimized single-file analysis.

        Args:
            file: File path to analyze.
            context: Context from previous batches (Temporal RAG).
            prompt: Specific instructions for this file.

        Returns:
            AnalysisResult object containing summary and insights.
        """
        return self.analyze_batch([file], context, prompt)

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the backend is available and configured correctly.

        Returns:
            True if available, False otherwise.
        """
        pass

    def _parse_output(self, raw_output: str) -> AnalysisResult:
        """Parse LLM response into structured result.

        This method provides a default robust parsing implementation that handles
        common LLM output formats (Markdown headers, lists, key-value pairs).
        Subclasses can override this if specific parsing logic is needed.

        Args:
            raw_output: Raw string output from the LLM/CLI.

        Returns:
            AnalysisResult object.
        """
        summary = ""
        insights = []
        questions = []
        current_section = None
        
        lines = raw_output.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for headers
            lower_line = line.lower()
            is_header = False
            
            # More robust header detection:
            # - Starts with # (Markdown)
            # - Ends with : (Key:)
            # - Contains : and is short (Key: Value)
            if line.startswith("#") or line.endswith(":") or (":" in line and len(line.split(":")[0]) < 20):
                if "summary" in lower_line:
                    current_section = "summary"
                    is_header = True
                    # If format is "Summary: Value", extract value immediately
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            summary += parts[1].strip() + "\n"
                elif "insight" in lower_line:
                    current_section = "insights"
                    is_header = True
                elif "question" in lower_line:
                    current_section = "questions"
                    is_header = True
            
            if is_header:
                 continue
                
            if current_section == "summary":
                summary += line + "\n"
            elif current_section == "insights":
                # Extract list items
                if line.startswith("- ") or line.startswith("* ") or (len(line) > 1 and line[0].isdigit() and line[1] in (".", ")")):
                    # Remove bullet points and numbering
                     cleaned = line.lstrip("-*1234567890.) ")
                     insights.append(cleaned)
            elif current_section == "questions":
                 if line.startswith("- ") or line.startswith("* ") or (len(line) > 1 and line[0].isdigit() and line[1] in (".", ")")):
                    cleaned = line.lstrip("-*1234567890.) ")
                    questions.append(cleaned)
                    
        return AnalysisResult(
            summary=summary.strip(),
            key_insights=insights,
            questions=questions,
            raw_output=raw_output
        )
