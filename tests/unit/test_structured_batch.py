"""Tests for structured batch analyzer."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from lantern_cli.llm.structured import (
    BatchInteraction,
    StructuredAnalyzer,
    StructuredAnalysisOutput,
    create_chain,
    _extract_json,
)


# ---------------------------------------------------------------------------
# create_chain
# ---------------------------------------------------------------------------

def test_create_chain_uses_with_structured_output() -> None:
    llm = MagicMock()
    llm.with_structured_output.return_value = RunnableLambda(
        lambda _: {"summary": "ok", "key_insights": [], "language": "en"}
    )
    schema = {"type": "object"}
    prompts = {"system": "sys", "user": "user {file_content}"}

    chain = create_chain(llm=llm, json_schema=schema, prompts=prompts)
    result = chain.invoke({"file_content": "x", "language": "en"})

    llm.with_structured_output.assert_called_once_with(schema)
    assert result["summary"] == "ok"


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
# StructuredAnalyzer.analyze_batch
# ---------------------------------------------------------------------------

class TestAnalyzeBatch:

    def test_normalizes_outputs(self) -> None:
        fake_chain = MagicMock()
        fake_chain.batch.return_value = [
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

        with patch("lantern_cli.llm.structured.create_chain", return_value=fake_chain):
            analyzer = StructuredAnalyzer(llm=MagicMock())
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

    def test_raises_runtime_error_on_chain_failure(self) -> None:
        fake_chain = MagicMock()
        fake_chain.batch.side_effect = Exception("API timeout")

        with patch("lantern_cli.llm.structured.create_chain", return_value=fake_chain):
            analyzer = StructuredAnalyzer(llm=MagicMock())
            with pytest.raises(RuntimeError, match="Structured batch analysis failed"):
                analyzer.analyze_batch([{"file_content": "x", "language": "en"}])


# ---------------------------------------------------------------------------
# StructuredAnalyzer.analyze (single-file convenience)
# ---------------------------------------------------------------------------

class TestAnalyzeSingle:

    def test_returns_single_output(self) -> None:
        fake_chain = MagicMock()
        fake_chain.batch.return_value = [
            {"summary": "single", "key_insights": ["k"], "language": "en"}
        ]

        with patch("lantern_cli.llm.structured.create_chain", return_value=fake_chain):
            analyzer = StructuredAnalyzer(llm=MagicMock())
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
