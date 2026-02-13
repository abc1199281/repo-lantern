"""Tests for CostTracker."""
import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.utils.cost_tracker import CostTracker, ModelPricing


class TestCostTracker:
    """Test CostTracker class."""

    SAMPLE_PRICING_JSON = {
        "models": {
            "gemini-1.5-flash": {
                "input_per_million": 0.075,
                "output_per_million": 0.30
            },
            "claude-sonnet-4": {
                "input_per_million": 3.0,
                "output_per_million": 15.0
            }
        }
    }

    @pytest.fixture
    def mock_urlopen(self):
        """Mock urllib.request.urlopen."""
        with patch("urllib.request.urlopen") as mock:
            # Setup successful response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = json.dumps(self.SAMPLE_PRICING_JSON).encode("utf-8")
            mock_response.__enter__.return_value = mock_response
            mock.return_value = mock_response
            yield mock

    @pytest.fixture
    def mock_urlopen_fail(self):
        """Mock urllib.request.urlopen failure."""
        with patch("urllib.request.urlopen") as mock:
            mock.side_effect = Exception("Network unavailable")
            yield mock

    def test_pricing_lookup_online(self, mock_urlopen) -> None:
        """Test fetching pricing from online source."""
        tracker = CostTracker("gemini-1.5-flash")
        
        # Verify fetch happened
        mock_urlopen.assert_called_once()
        
        # Verify value
        assert tracker.pricing is not None
        assert tracker.pricing.input_per_million == 0.075
        assert tracker.pricing.output_per_million == 0.30

    def test_pricing_lookup_offline(self, mock_urlopen_fail) -> None:
        """Test behavior when network is unavailable."""
        tracker = CostTracker("gemini-1.5-flash")
        
        # Verify tried to fetch
        mock_urlopen_fail.assert_called_once()
        
        # Verify pricing is None
        assert tracker.pricing is None

    def test_estimate_tokens(self) -> None:
        """Test token estimation."""
        with patch("urllib.request.urlopen"): # patch to avoid network call
            tracker = CostTracker()
        # 100 characters ≈ 25 tokens (1 token = 4 chars)
        text = "a" * 100
        tokens = tracker.estimate_tokens(text)
        assert tokens == 25

    def test_estimate_file_tokens(self, tmp_path: Path) -> None:
        """Test file token estimation."""
        with patch("urllib.request.urlopen"):
            tracker = CostTracker()

        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        tokens = tracker.estimate_file_tokens(str(test_file))
        assert tokens == 8

    def test_estimate_batch_cost_online(self, tmp_path: Path, mock_urlopen) -> None:
        """Test batch cost estimation with online data."""
        tracker = CostTracker("gemini-1.5-flash")

        # Create test files
        file1 = tmp_path / "file1.py"
        file1.write_text("x" * 400)  # 100 tokens

        file2 = tmp_path / "file2.py"
        file2.write_text("y" * 400)  # 100 tokens

        context = "z" * 400  # 100 tokens
        prompt = "Analyze these files"  # ~5 tokens

        result = tracker.estimate_batch_cost(
            files=[str(file1), str(file2)], context=context, prompt=prompt
        )
        
        assert result is not None
        total_tokens, cost = result

        # Input: 100 + 100 + 100 + 5 = 305 tokens
        assert 350 <= total_tokens <= 450

        # Cost should be very small
        assert 0.00001 <= cost <= 0.001

    def test_estimate_batch_cost_offline(self, tmp_path: Path, mock_urlopen_fail) -> None:
        """Test batch cost estimation returns None when offline."""
        tracker = CostTracker("gemini-1.5-flash")

        result = tracker.estimate_batch_cost(
            files=["dummy.py"], context="", prompt=""
        )
        
        assert result is None

    def test_record_usage_and_get_total_cost(self, mock_urlopen) -> None:
        """Test recording actual usage and calculating total cost."""
        tracker = CostTracker("gemini-1.5-flash")

        # Record 1M input tokens and 1M output tokens
        tracker.record_usage(input_tokens=1_000_000, output_tokens=1_000_000)

        total_cost = tracker.get_total_cost()
        # $0.075 (input) + $0.30 (output) = $0.375
        assert 0.37 <= total_cost <= 0.38
        
        # Verify report generation
        report = tracker.get_report()
        assert "gemini-1.5-flash" in report
        assert "$" in report

    def test_record_usage_offline(self, mock_urlopen_fail) -> None:
        """Test that usage recording works offline but cost is 0."""
        tracker = CostTracker("gemini-1.5-flash")
        
        tracker.record_usage(input_tokens=1000, output_tokens=1000)
        
        # Usage stats should still update
        assert tracker.usage.input_tokens == 1000
        
        # But cost should be 0.0 because pricing is unknown
        assert tracker.get_total_cost() == 0.0

    def test_local_model_free(self, mock_urlopen) -> None:
        """Test that local models are free and don't fetch pricing."""
        tracker = CostTracker("llama3", is_local=True)
        
        # Should not have called urlopen
        mock_urlopen.assert_not_called()
        
        # Pricing should be 0
        assert tracker.pricing is not None
        assert tracker.pricing.input_per_million == 0.0
        assert tracker.pricing.output_per_million == 0.0
        
        # Estimation should be $0
        result = tracker.estimate_batch_cost(["foo.py"], "", "")
        assert result is not None
        _, cost = result
        assert cost == 0.0
