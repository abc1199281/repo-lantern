"""Base classes for LLM backend adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    """Unified analysis payload used by runner/memory flow."""

    summary: str
    key_insights: list[str] = field(default_factory=list)
    raw_output: str = ""


class BackendAdapter(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    def get_llm(self) -> Any:
        """Return a configured provider LLM client."""
        raise NotImplementedError

    def invoke(self, prompt: str) -> str:
        """Invoke the backend LLM with a plain-text prompt and return plain text.

        This is intentionally shared in the base class to keep core logic free of
        provider-specific response types. Subclasses only need to implement
        `get_llm()` (LangChain chat model).
        """
        llm = self.get_llm()
        response = llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content)

    def summarize_batch(self, files: list[str], context: str, prompt: str) -> AnalysisResult:
        """Summarize a batch (aggregate output).

        Default implementation uses `invoke()` and returns an `AnalysisResult`.
        Backends may override this if they can do better parsing/formatting.
        """
        # Keep this minimal; file reading/prompt building belongs in core.
        raw_output = self.invoke(prompt if not context else f"{prompt}\n\nContext:\n{context}")
        return AnalysisResult(summary=raw_output.strip(), key_insights=[], raw_output=raw_output.strip())

    def analyze_batch(self, files: list[str], context: str, prompt: str) -> AnalysisResult:
        """Backward-compatible alias for `summarize_batch`.

        Prefer calling `summarize_batch` to avoid confusion with structured
        per-item batch execution (`StructuredAnalyzer.analyze_batch`).
        """
        return self.summarize_batch(files=files, context=context, prompt=prompt)
