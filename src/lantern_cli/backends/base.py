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
