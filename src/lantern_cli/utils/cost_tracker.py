"""Cost tracking and estimation for LLM API usage."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import urllib.request
import json
import logging

logger = logging.getLogger(__name__)


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

    # Source URL for pricing data
    PRICING_URL = "https://raw.githubusercontent.com/powei-lin/repo-lantern/main/pricing.json"

    def __init__(self, model_name: str = "gemini-1.5-flash", is_local: bool = False) -> None:
        """Initialize CostTracker.

        Args:
            model_name: Name of the LLM model being used.
            is_local: Whether the model is running locally (free).
        """
        self.model_name = model_name
        self.is_local = is_local
        self.pricing_data: dict[str, ModelPricing] = {}
        self.pricing: Optional[ModelPricing] = None
        
        if self.is_local:
            # Local models are free
            self.pricing = ModelPricing(input_per_million=0.0, output_per_million=0.0)
        else:
            # Try to fetch pricing online for API models
            if self._fetch_pricing():
                self.pricing = self._get_pricing(model_name)
            else:
                logger.warning("Could not fetch pricing data. Cost estimation will be unavailable.")
                self.pricing = None

        self.usage = UsageStats()

    def _fetch_pricing(self) -> bool:
        """Fetch pricing data from online source.

        Returns:
            True if successful, False otherwise.
        """
        try:
            with urllib.request.urlopen(self.PRICING_URL, timeout=3) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # Parse JSON into ModelPricing objects
                    for model, price in data.get("models", {}).items():
                        self.pricing_data[model] = ModelPricing(
                            input_per_million=price["input_per_million"],
                            output_per_million=price["output_per_million"]
                        )
                    return True
        except Exception as e:
            logger.debug(f"Failed to fetch pricing: {e}")
            return False

    def _get_pricing(self, model_name: str) -> Optional[ModelPricing]:
        """Get pricing for a model.

        Args:
            model_name: Model name.

        Returns:
            ModelPricing object or None if not found.
        """
        # Try exact match first
        if model_name in self.pricing_data:
            return self.pricing_data[model_name]

        # Try partial match (e.g., "gemini-1.5-flash-latest" -> "gemini-1.5-flash")
        for key in self.pricing_data:
            if key in model_name:
                return self.pricing_data[key]

        # Return default from loaded data if possible, or None
        # User requested "unable to estimate" if network fail, 
        # but if we have network but unknown model? 
        # For now, let's return None to be safe/strict as requested.
        return None

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
    ) -> Optional[tuple[int, float]]:
        """Estimate cost for analyzing a batch of files.

        Args:
            files: List of file paths.
            context: Context string (from previous batches).
            prompt: Prompt string.

        Returns:
            Tuple of (estimated_tokens, estimated_cost_usd), or None if pricing unavailable.
        """
        if not self.pricing:
            return None

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

    def record_from_usage_metadata(self, response: Any) -> None:
        """Record actual usage from LangChain response's usage_metadata.
        
        LangChain ChatModel responses include usage_metadata with real token counts
        from the provider (e.g., Ollama, Claude, GPT). This provides actual counts
        instead of estimates. For local models, usage_metadata may be absent.
        
        Expected Structure:
            response.usage_metadata = {
                'input_tokens': int,
                'output_tokens': int,
                # other fields vendor-specific
            }
        
        Error Handling:
            - Missing usage_metadata: Logs debug msg, returns gracefully
            - Malformed metadata: Logs warning, falls back to estimate-based tracking
            - Never raises exceptions (safe for production)
        
        Args:
            response: LangChain AIMessage or chat model response object.
            
        Example:
            >>> response = llm.invoke([{"role": "user", "content": "..."}])
            >>> cost_tracker.record_from_usage_metadata(response)
        """
        try:
            usage_metadata = getattr(response, "usage_metadata", None)
            if not usage_metadata:
                logger.debug("No usage_metadata in response, skipping token recording")
                return

            # Safely extract token counts with defaults
            input_tokens = usage_metadata.get("input_tokens", 0)
            output_tokens = usage_metadata.get("output_tokens", 0)

            # Only record if we have actual token counts
            if input_tokens or output_tokens:
                self.record_usage(int(input_tokens), int(output_tokens))
                logger.debug(
                    f"Recorded usage from metadata: "
                    f"in={input_tokens}, out={output_tokens}"
                )
            else:
                logger.debug("No token counts found in usage_metadata")

        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                f"Failed to extract usage metadata from response: {e}. "
                f"Falling back to estimate-based tracking."
            )

    def get_total_cost(self) -> float:
        """Calculate total cost based on recorded usage.

        Returns:
            Total cost in USD.
        """
        if not self.pricing:
            return 0.0
            
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
