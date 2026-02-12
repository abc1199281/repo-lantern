"""Tests for CostTracker."""
import tempfile
from pathlib import Path

import pytest

from lantern_cli.utils.cost_tracker import CostTracker, ModelPricing


class TestCostTracker:
    """Test CostTracker class."""

    def test_pricing_lookup_exact(self) -> None:
        """Test exact model name match."""
        tracker = CostTracker("gemini-1.5-flash")
        assert tracker.pricing.input_per_million == 0.075
        assert tracker.pricing.output_per_million == 0.30

    def test_pricing_lookup_partial(self) -> None:
        """Test partial model name match."""
        tracker = CostTracker("gemini-1.5-flash-latest")
        assert tracker.pricing.input_per_million == 0.075

    def test_pricing_lookup_unknown(self) -> None:
        """Test unknown model uses default pricing."""
        tracker = CostTracker("unknown-model-xyz")
        assert tracker.pricing.input_per_million == 2.0
        assert tracker.pricing.output_per_million == 8.0

    def test_estimate_tokens(self) -> None:
        """Test token estimation."""
        tracker = CostTracker()
        # 100 characters ≈ 25 tokens (1 token = 4 chars)
        text = "a" * 100
        tokens = tracker.estimate_tokens(text)
        assert tokens == 25

    def test_estimate_file_tokens(self, tmp_path: Path) -> None:
        """Test file token estimation."""
        tracker = CostTracker()

        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        tokens = tracker.estimate_file_tokens(str(test_file))
        assert tokens > 0
        # 32 characters / 4 = 8 tokens
        assert tokens == 8

    def test_estimate_file_tokens_nonexistent(self) -> None:
        """Test estimation for nonexistent file returns 0."""
        tracker = CostTracker()
        tokens = tracker.estimate_file_tokens("/nonexistent/file.py")
        assert tokens == 0

    def test_estimate_batch_cost(self, tmp_path: Path) -> None:
        """Test batch cost estimation."""
        tracker = CostTracker("gemini-1.5-flash")

        # Create test files
        file1 = tmp_path / "file1.py"
        file1.write_text("x" * 400)  # 100 tokens

        file2 = tmp_path / "file2.py"
        file2.write_text("y" * 400)  # 100 tokens

        context = "z" * 400  # 100 tokens
        prompt = "Analyze these files"  # ~5 tokens

        total_tokens, cost = tracker.estimate_batch_cost(
            files=[str(file1), str(file2)], context=context, prompt=prompt
        )

        # Input: 100 + 100 + 100 + 5 = 305 tokens
        # Output: ~305 * 0.3 = 91 tokens
        # Total: ~396 tokens
        assert 350 <= total_tokens <= 450

        # Cost should be very small with Flash (< $0.001)
        assert 0.00001 <= cost <= 0.001

    def test_record_usage(self) -> None:
        """Test recording actual usage."""
        tracker = CostTracker()

        tracker.record_usage(input_tokens=1000, output_tokens=300)
        assert tracker.usage.input_tokens == 1000
        assert tracker.usage.output_tokens == 300
        assert tracker.usage.api_calls == 1

        tracker.record_usage(input_tokens=500, output_tokens=200)
        assert tracker.usage.input_tokens == 1500
        assert tracker.usage.output_tokens == 500
        assert tracker.usage.api_calls == 2

    def test_get_total_cost(self) -> None:
        """Test total cost calculation."""
        tracker = CostTracker("gemini-1.5-flash")

        # Record 1M input tokens and 1M output tokens
        tracker.record_usage(input_tokens=1_000_000, output_tokens=1_000_000)

        total_cost = tracker.get_total_cost()
        # $0.075 (input) + $0.30 (output) = $0.375
        assert 0.37 <= total_cost <= 0.38

    def test_get_report(self) -> None:
        """Test cost report generation."""
        tracker = CostTracker("gpt-4o")
        tracker.record_usage(input_tokens=10_000, output_tokens=3_000)

        report = tracker.get_report()

        assert "gpt-4o" in report
        assert "10,000" in report
        assert "3,000" in report
        assert "13,000" in report  # Total tokens
        assert "$" in report

    def test_multiple_models_pricing(self) -> None:
        """Test pricing for various models."""
        models_to_test = [
            ("claude-sonnet-4", 3.0, 15.0),
            ("gpt-4o-mini", 0.15, 0.60),
            ("gemini-2.0-flash", 0.10, 0.40),
        ]

        for model_name, expected_input, expected_output in models_to_test:
            tracker = CostTracker(model_name)
            assert tracker.pricing.input_per_million == expected_input
            assert tracker.pricing.output_per_million == expected_output
