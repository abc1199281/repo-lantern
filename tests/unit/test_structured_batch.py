"""Tests for structured batch analyzer."""

from unittest.mock import MagicMock

import pytest

from lantern_cli.llm.structured import (
    BatchInteraction,
    StructuredAnalysisOutput,
    StructuredAnalyzer,
    _extract_json,
)

# ---------------------------------------------------------------------------
# StructuredAnalysisOutput normalisation
# ---------------------------------------------------------------------------


class TestStructuredAnalysisOutput:
    """Test Pydantic model normalisation / defaults."""

    def test_defaults_for_optional_fields(self) -> None:
        out = StructuredAnalysisOutput(summary="s", key_insights=["a"], language="en")
        assert out.functions == []
        assert out.classes == []
        assert out.flow is None
        assert out.flow_diagram is None
        assert out.references == []

    def test_whitespace_trimming(self) -> None:
        out = StructuredAnalysisOutput(
            summary="  hello  ",
            key_insights=["  a  ", "  b  "],
            language="  en  ",
        )
        assert out.summary == "hello"
        assert out.key_insights == ["a", "b"]
        assert out.language == "en"

    def test_max_items_enforced(self) -> None:
        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[f"item{i}" for i in range(20)],
            functions=[f"f{i}" for i in range(10)],
            language="en",
        )
        assert len(out.key_insights) <= 8
        assert len(out.functions) <= 5

    def test_missing_language_defaults_to_en(self) -> None:
        out = StructuredAnalysisOutput(summary="s", key_insights=[])
        assert out.language == "en"


# ---------------------------------------------------------------------------
# StructuredAnalyzer._to_payload
# ---------------------------------------------------------------------------


class TestToPayload:

    def test_dict_passthrough(self) -> None:
        d = {"summary": "hi"}
        assert StructuredAnalyzer._to_payload(d) == d

    def test_pydantic_model(self) -> None:
        out = StructuredAnalysisOutput(summary="s", key_insights=[], language="en")
        result = StructuredAnalyzer._to_payload(out)
        assert isinstance(result, dict)
        assert result["summary"] == "s"

    def test_json_string(self) -> None:
        result = StructuredAnalyzer._to_payload('{"summary": "s"}')
        assert result == {"summary": "s"}

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            StructuredAnalyzer._to_payload(42)


# ---------------------------------------------------------------------------
# StructuredAnalyzer._to_text
# ---------------------------------------------------------------------------


class TestToText:

    def test_string_passthrough(self) -> None:
        assert StructuredAnalyzer._to_text("hello") == "hello"

    def test_dict_to_json(self) -> None:
        result = StructuredAnalyzer._to_text({"a": 1})
        assert '"a": 1' in result

    def test_pydantic_model_to_json(self) -> None:
        out = StructuredAnalysisOutput(summary="s", key_insights=[], language="en")
        result = StructuredAnalyzer._to_text(out)
        assert "summary" in result

    def test_arbitrary_to_str(self) -> None:
        assert StructuredAnalyzer._to_text(42) == "42"


# ---------------------------------------------------------------------------
# _extract_json helper
# ---------------------------------------------------------------------------


class TestExtractJson:

    def test_plain_json(self) -> None:
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_fenced_json(self) -> None:
        result = _extract_json('```json\n{"a": 1}\n```')
        assert '"a": 1' in result

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not extract"):
            _extract_json("no json here")


# ---------------------------------------------------------------------------
# StructuredAnalyzer.analyze_batch (now uses Backend protocol)
# ---------------------------------------------------------------------------


class TestAnalyzeBatch:

    def test_normalizes_outputs(self) -> None:
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {
                "summary": "  summary  ",
                "key_insights": [" A ", "B"],
                "functions": ["f1"],
                "classes": [],
                "flow": " flow ",
                "references": ["src/a.py"],
                "language": "",
            },
            '{"summary":"s2","key_insights":[],"language":"zh-TW"}',
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch(
            [
                {"file_content": "a", "language": "en"},
                {"file_content": "b", "language": "zh-TW"},
            ]
        )

        assert len(interactions) == 2
        assert isinstance(interactions[0], BatchInteraction)
        assert interactions[0].analysis.summary == "summary"
        assert interactions[0].analysis.key_insights == ["A", "B"]
        assert interactions[0].analysis.flow == "flow"
        assert interactions[0].analysis.language == "en"
        assert interactions[1].analysis.language == "zh-TW"

    def test_overrides_llm_language_with_requested_language(self) -> None:
        """Verify that LLM's returned language is always overridden with requested language."""
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {"summary": "s1", "key_insights": [], "language": "es"},  # LLM returned wrong language
            {"summary": "s2", "key_insights": [], "language": "fr"},  # LLM returned wrong language
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch(
            [
                {"file_content": "a", "language": "en"},
                {"file_content": "b", "language": "zh-TW"},
            ]
        )

        # Should use requested language, not LLM's returned language
        assert interactions[0].analysis.language == "en"
        assert interactions[1].analysis.language == "zh-TW"

    def test_raises_runtime_error_on_backend_failure(self) -> None:
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.side_effect = Exception("API timeout")

        analyzer = StructuredAnalyzer(backend=mock_backend)
        with pytest.raises(RuntimeError, match="Structured batch analysis failed"):
            analyzer.analyze_batch([{"file_content": "x", "language": "en"}])


# ---------------------------------------------------------------------------
# StructuredAnalyzer.analyze (single-file convenience)
# ---------------------------------------------------------------------------


class TestAnalyzeSingle:

    def test_returns_single_output(self) -> None:
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {"summary": "single", "key_insights": ["k"], "language": "en"}
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        result = analyzer.analyze("def f(): pass", "en")

        assert isinstance(result, StructuredAnalysisOutput)
        assert result.summary == "single"


# ---------------------------------------------------------------------------
# BatchInteraction.to_dict
# ---------------------------------------------------------------------------


def test_batch_interaction_to_dict() -> None:
    analysis = StructuredAnalysisOutput(summary="s", key_insights=["k"], language="en")
    interaction = BatchInteraction(
        prompt_payload={"file_content": "code", "language": "en"},
        raw_response="raw",
        analysis=analysis,
    )
    d = interaction.to_dict()
    assert d["prompt"] == {"file_content": "code", "language": "en"}
    assert d["raw_response"] == "raw"
    assert d["analysis"]["summary"] == "s"


# ---------------------------------------------------------------------------
# StructuredAnalyzer Mermaid Repair Logic
# ---------------------------------------------------------------------------


class TestMermaidRepair:
    """Test Mermaid diagram repair when validation fails."""

    def test_repair_triggered_when_validation_fails(self) -> None:
        """If flow_diagram fails validation, trigger LLM repair."""
        # First call: batch_invoke_structured returns invalid diagram
        # Second call (in repair): invoke returns valid diagram
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {
                "summary": "s",
                "key_insights": [],
                "flow_diagram": "this is not valid mermaid",
            }
        ]
        from lantern_cli.llm.backend import LLMResponse

        mock_backend.invoke.return_value = LLMResponse(
            content="graph TD\n    A --> B", usage_metadata=None
        )

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Repair was triggered (invoke was called)
        assert mock_backend.invoke.called
        # flow_diagram should be set to the repaired value
        assert interactions[0].analysis.flow_diagram == "graph TD\n    A --> B"

    def test_repair_not_triggered_when_valid(self) -> None:
        """If flow_diagram is valid, don't trigger repair."""
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {
                "summary": "s",
                "key_insights": [],
                "flow_diagram": "graph TD\n    A --> B",
            }
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Repair should NOT have been triggered
        assert not mock_backend.invoke.called
        # flow_diagram should be preserved
        assert interactions[0].analysis.flow_diagram == "graph TD\n    A --> B"

    def test_repair_not_triggered_when_absent(self) -> None:
        """If flow_diagram is absent, don't trigger repair."""
        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [{"summary": "s", "key_insights": []}]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Repair should NOT have been triggered
        assert not mock_backend.invoke.called
        assert interactions[0].analysis.flow_diagram is None

    def test_repair_succeeds_on_second_attempt(self) -> None:
        """If first repair attempt fails, retry up to max_retries."""
        from lantern_cli.llm.backend import LLMResponse

        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {
                "summary": "s",
                "key_insights": [],
                "flow_diagram": "invalid mermaid",
            }
        ]
        # First repair attempt: invalid, second: valid
        mock_backend.invoke.side_effect = [
            LLMResponse(content="still invalid", usage_metadata=None),
            LLMResponse(content="graph LR\n    A --> B", usage_metadata=None),
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend, mermaid_repair_retries=2)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Should have called invoke twice
        assert mock_backend.invoke.call_count == 2
        # flow_diagram should be set to the second (valid) attempt
        assert interactions[0].analysis.flow_diagram == "graph LR\n    A --> B"

    def test_repair_fails_all_retries(self) -> None:
        """If all repair attempts fail, flow_diagram stays None."""
        from lantern_cli.llm.backend import LLMResponse

        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {
                "summary": "s",
                "key_insights": [],
                "flow_diagram": "invalid diagram",
            }
        ]
        # All repair attempts return invalid content
        mock_backend.invoke.side_effect = [
            LLMResponse(content="still bad", usage_metadata=None),
            LLMResponse(content="also bad", usage_metadata=None),
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend, mermaid_repair_retries=2)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Should have tried twice
        assert mock_backend.invoke.call_count == 2
        # flow_diagram should be None since all repairs failed
        assert interactions[0].analysis.flow_diagram is None

    def test_repair_retries_configurable(self) -> None:
        """Test that mermaid_repair_retries parameter is respected."""
        from lantern_cli.llm.backend import LLMResponse

        mock_backend = MagicMock()
        mock_backend.batch_invoke_structured.return_value = [
            {"summary": "s", "key_insights": [], "flow_diagram": "bad"}
        ]
        mock_backend.invoke.return_value = LLMResponse(content="invalid", usage_metadata=None)

        # Try with 3 retries
        analyzer = StructuredAnalyzer(backend=mock_backend, mermaid_repair_retries=3)
        analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Should have called invoke 3 times
        assert mock_backend.invoke.call_count == 3

    def test_individually_analyze_triggers_repair(self) -> None:
        """Test that repair also works in _analyze_batch_individually fallback."""
        from lantern_cli.llm.backend import LLMResponse

        mock_backend = MagicMock()
        # Batch invoke raises length limit error → fallback to individual
        mock_backend.batch_invoke_structured.side_effect = RuntimeError("length limit exceeded")
        # Individual invoke returns invalid diagram
        mock_backend.invoke.side_effect = [
            LLMResponse(
                content='{"summary":"s","key_insights":[],"flow_diagram":"bad"}',
                usage_metadata=None,
            ),
            # Repair attempt
            LLMResponse(content="graph TD\n    X --> Y", usage_metadata=None),
        ]

        analyzer = StructuredAnalyzer(backend=mock_backend)
        interactions = analyzer.analyze_batch([{"file_content": "code", "language": "en"}])

        # Should have called invoke: once for analysis, once for repair
        assert mock_backend.invoke.call_count == 2
        # Diagram should be repaired
        assert interactions[0].analysis.flow_diagram == "graph TD\n    X --> Y"
