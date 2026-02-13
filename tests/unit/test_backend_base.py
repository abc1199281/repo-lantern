"""Tests for Backend Adapter Interface."""
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


@dataclass
class MockAdapter(BackendAdapter):
    """Mock adapter for testing interface."""

    def analyze_batch(self, files: list[str], context: str, prompt: str) -> AnalysisResult:
        """Mock analyze."""
        return AnalysisResult(
            summary="Mock summary",
            key_insights=["Insight 1"],
            questions=[],
            raw_output="raw",
        )

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Mock synthesize."""
        return "Synthesized content"

    def health_check(self) -> bool:
        """Mock health check."""
        return True


class TestBackendAdapterInterface:
    """Test BackendAdapter interface contract."""

    def test_analysis_result_structure(self) -> None:
        """Test AnalysisResult dataclass."""
        result = AnalysisResult(
            summary="Test",
            key_insights=["A", "B"],
            questions=["Q1"],
            raw_output="Raw",
        )
        assert result.summary == "Test"
        assert len(result.key_insights) == 2
        assert len(result.questions) == 1
        assert result.raw_output == "Raw"

    def test_adapter_instantiation(self) -> None:
        """Test that concrete adapter can be instantiated."""
        adapter = MockAdapter()
        assert isinstance(adapter, BackendAdapter)

    def test_abstract_methods(self) -> None:
        """Test that abstract methods raise error if not implemented."""
        class IncompleteAdapter(BackendAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore

    def test_contract_execution(self) -> None:
        """Test execution of interface methods."""
        adapter = MockAdapter()
        # Mock analyze_batch is used here, not the base _parse_output
        result = adapter.analyze_batch([], "", "")
        assert isinstance(result, AnalysisResult)
        assert result.summary == "Mock summary"
        
        synth = adapter.synthesize([], "en")
        assert synth == "Synthesized content"
        
        assert adapter.health_check() is True

    def test_parse_output_markdown_headers(self) -> None:
        """Test parsing with Markdown headers."""
        adapter = MockAdapter()
        raw = """
# Summary
This is the summary.

# Key Insights
- Insight 1
- Insight 2

# Questions
- Question 1
"""
        result = adapter._parse_output(raw)
        assert result.summary == "This is the summary."
        assert result.key_insights == ["Insight 1", "Insight 2"]
        assert result.questions == ["Question 1"]

    def test_parse_output_colon_format(self) -> None:
        """Test parsing with 'Key:' format."""
        adapter = MockAdapter()
        raw = """
Summary:
Short summary.

Key Insights:
* Insight 1

Questions:
1. Q1
"""
        result = adapter._parse_output(raw)
        assert result.summary == "Short summary."
        assert result.key_insights == ["Insight 1"]
        assert result.questions == ["Q1"]

    def test_parse_output_inline_summary(self) -> None:
        """Test parsing 'Summary: content' on same line."""
        adapter = MockAdapter()
        raw = """
Summary: Inline summary content.
Insights:
- I1
"""
        result = adapter._parse_output(raw)
        assert result.summary == "Inline summary content."
        assert result.key_insights == ["I1"]
        
    def test_parse_output_fallback(self) -> None:
        """Test parsing fallback for unstructured text."""
        adapter = MockAdapter()
        raw = "Just raw text."
        result = adapter._parse_output(raw)
        # Current logic doesn't fallback summary to raw_text unless explicitly handled
        # But wait, looking at my implementation:
        # if current_section == "summary": summary += line
        # It won't capture anything if no header found.
        # Let's verify this behavior.
        assert result.summary == ""
        assert result.raw_output == "Just raw text."
