"""Backend Protocol for LLM abstraction.

Defines the minimal interface that all LLM backends must implement.
Consumers (Runner, MemoryManager, StructuredAnalyzer) depend on this
Protocol instead of LangChain-specific classes.

Response Contract:
- invoke() returns LLMResponse with .content (str) and .usage_metadata (dict | None)
- batch_invoke_structured() returns list of raw responses (dict, BaseModel, or str)
  that StructuredAnalyzer._to_payload() can handle
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Standardised response from any LLM backend.

    Attributes:
        content: The text content of the response.
        usage_metadata: Optional token usage dict with 'input_tokens' and
            'output_tokens' keys.  Backends that cannot report usage
            (e.g. CLI) should set this to ``None``.
    """

    content: str
    usage_metadata: dict[str, int] | None = None


@runtime_checkable
class Backend(Protocol):
    """Minimal interface for LLM backends.

    Three operations cover all current consumers:

    1. ``invoke``  – plain text generation (MemoryManager compression)
    2. ``batch_invoke_structured`` – batch structured output (StructuredAnalyzer)
    3. ``model_name`` – identifier for cost tracking / logging
    """

    def invoke(self, prompt: str) -> LLMResponse:
        """Generate a plain-text response.

        Args:
            prompt: The prompt string.

        Returns:
            LLMResponse with content and optional usage metadata.
        """
        ...

    def batch_invoke_structured(
        self,
        items: list[dict[str, str]],
        json_schema: dict[str, Any],
        prompts: dict[str, str],
    ) -> list[Any]:
        """Run batch structured-output generation.

        Each item is a dict (e.g. ``{"file_content": ..., "language": ...}``)
        that will be formatted into the prompt template defined by *prompts*.

        Args:
            items: List of input dicts, one per file.
            json_schema: JSON Schema the output must conform to.
            prompts: Dict with ``"system"`` and ``"user"`` prompt templates.

        Returns:
            List of raw responses in the same order as *items*.  Each
            element may be a ``dict``, a Pydantic ``BaseModel``, or a
            JSON ``str`` – callers are expected to normalise via
            ``StructuredAnalyzer._to_payload``.
        """
        ...

    @property
    def model_name(self) -> str:
        """Model identifier used for cost tracking and display."""
        ...
