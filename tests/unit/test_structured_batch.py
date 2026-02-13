"""Tests for structured batch analyzer."""

from unittest.mock import MagicMock, patch

from langchain_core.runnables import RunnableLambda

from lantern_cli.llm.structured import (
    BatchInteraction,
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
