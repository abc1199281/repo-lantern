"""Cost tracking and estimation for LLM API usage."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ModelPricing:
    """Pricing information for a model."""

    input_per_million: float  # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens


@dataclass
class UsageStats:
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0


class CostTracker:
    """Track and estimate LLM API costs."""

    # Pricing as of 2026-02 (USD per 1M tokens)
    PRICING = {
        "gemini-1.5-flash": ModelPricing(input_per_million=0.075, output_per_million=0.30),
        "gemini-1.5-flash-8b": ModelPricing(
            input_per_million=0.0375, output_per_million=0.15
        ),
        "gemini-1.5-pro": ModelPricing(input_per_million=1.25, output_per_million=5.00),
        "gemini-2.0-flash": ModelPricing(input_per_million=0.10, output_per_million=0.40),
        "claude-sonnet-4": ModelPricing(input_per_million=3.0, output_per_million=15.0),
        "claude-haiku-3.5": ModelPricing(input_per_million=0.80, output_per_million=4.00),
        "claude-opus-4": ModelPricing(input_per_million=15.0, output_per_million=75.0),
        "gpt-4o": ModelPricing(input_per_million=2.5, output_per_million=10.0),
        "gpt-4o-mini": ModelPricing(input_per_million=0.15, output_per_million=0.60),
        "gpt-4-turbo": ModelPricing(input_per_million=10.0, output_per_million=30.0),
    }

    # Default pricing for unknown models (conservative estimate)
    DEFAULT_PRICING = ModelPricing(input_per_million=2.0, output_per_million=8.0)

    def __init__(self, model_name: str = "gemini-1.5-flash") -> None:
        """Initialize CostTracker.

        Args:
            model_name: Name of the LLM model being used.
        """
        self.model_name = model_name
        self.pricing = self._get_pricing(model_name)
        self.usage = UsageStats()

    def _get_pricing(self, model_name: str) -> ModelPricing:
        """Get pricing for a model.

        Args:
            model_name: Model name.

        Returns:
            ModelPricing object.
        """
        # Try exact match first
        if model_name in self.PRICING:
            return self.PRICING[model_name]

        # Try partial match (e.g., "gemini-1.5-flash-latest" -> "gemini-1.5-flash")
        for key in self.PRICING:
            if key in model_name:
                return self.PRICING[key]

        # Return default
        return self.DEFAULT_PRICING

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses simple heuristic: 1 token ≈ 4 characters.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        return len(text) // 4

    def estimate_file_tokens(self, file_path: str) -> int:
        """Estimate tokens for a file.

        Args:
            file_path: Path to file.

        Returns:
            Estimated token count, or 0 if file cannot be read.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                return self.estimate_tokens(content)
        except (OSError, UnicodeDecodeError):
            # Binary file or cannot read
            return 0

    def estimate_batch_cost(
        self, files: list[str], context: str = "", prompt: str = ""
    ) -> tuple[int, float]:
        """Estimate cost for analyzing a batch of files.

        Args:
            files: List of file paths.
            context: Context string (from previous batches).
            prompt: Prompt string.

        Returns:
            Tuple of (estimated_tokens, estimated_cost_usd).
        """
        # Input tokens = files + context + prompt
        input_tokens = 0
        for file_path in files:
            input_tokens += self.estimate_file_tokens(file_path)

        input_tokens += self.estimate_tokens(context)
        input_tokens += self.estimate_tokens(prompt)

        # Output tokens: rough estimate based on input
        # Typically LLM output is 20-40% of input for analysis tasks
        output_tokens = int(input_tokens * 0.3)

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.pricing.input_per_million
        output_cost = (output_tokens / 1_000_000) * self.pricing.output_per_million
        total_cost = input_cost + output_cost

        return (input_tokens + output_tokens, total_cost)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record actual token usage.

        Args:
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
        """
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens
        self.usage.api_calls += 1

    def get_total_cost(self) -> float:
        """Calculate total cost based on recorded usage.

        Returns:
            Total cost in USD.
        """
        input_cost = (self.usage.input_tokens / 1_000_000) * self.pricing.input_per_million
        output_cost = (
            self.usage.output_tokens / 1_000_000
        ) * self.pricing.output_per_million
        return input_cost + output_cost

    def get_report(self) -> str:
        """Generate human-readable cost report.

        Returns:
            Formatted report string.
        """
        total_cost = self.get_total_cost()
        total_tokens = self.usage.input_tokens + self.usage.output_tokens

        lines = [
            "💰 Cost Report",
            f"   Model: {self.model_name}",
            f"   API Calls: {self.usage.api_calls}",
            f"   Input Tokens: {self.usage.input_tokens:,}",
            f"   Output Tokens: {self.usage.output_tokens:,}",
            f"   Total Tokens: {total_tokens:,}",
            f"   Total Cost: ${total_cost:.4f}",
        ]

        return "\n".join(lines)
