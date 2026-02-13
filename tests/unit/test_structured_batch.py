"""Tests for structured batch analyzer."""

from unittest.mock import MagicMock, patch

from langchain_core.runnables import RunnableLambda

from lantern_cli.llm.structured import (
    StructuredAnalyzer,
    StructuredAnalysisOutput,
    create_chain,
)


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


def test_analyze_batch_normalizes_outputs() -> None:
    fake_chain = MagicMock()
    fake_chain.batch.return_value = [
        {
            "summary": "  summary  ",
            "key_insights": [" A ", "B"],
            "functions": ["f1"],
            "classes": [],
            "flow": " flow ",
            "risks": ["r1"],
            "references": ["src/a.py"],
            "language": "",
        },
        '{"summary":"s2","key_insights":[],"language":"zh-TW"}',
    ]

    with patch("lantern_cli.llm.structured.create_chain", return_value=fake_chain):
        analyzer = StructuredAnalyzer(llm=MagicMock())
        outputs = analyzer.analyze_batch(
            [
                {"file_content": "a", "language": "en"},
                {"file_content": "b", "language": "zh-TW"},
            ]
        )

    assert len(outputs) == 2
    assert isinstance(outputs[0], StructuredAnalysisOutput)
    assert outputs[0].summary == "summary"
    assert outputs[0].key_insights == ["A", "B"]
    assert outputs[0].flow == "flow"
    assert outputs[0].language == "en"
    assert outputs[1].language == "zh-TW"

