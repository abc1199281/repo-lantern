"""Tests for Runner bottom-up structured batch flow."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lantern_cli.backends.base import AnalysisResult
from lantern_cli.core.architect import Batch
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import ExecutionState
from lantern_cli.llm.structured import BatchInteraction, StructuredAnalysisOutput


def _make_runner(tmp_path: Path) -> tuple[Runner, MagicMock]:
    backend = MagicMock()
    backend.get_llm.return_value = MagicMock()
    state_manager = MagicMock()
    state_manager.state = ExecutionState(global_summary="old")
    runner = Runner(root_path=tmp_path, backend=backend, state_manager=state_manager)
    return runner, backend


def test_generate_bottom_up_doc_uses_batch_once(tmp_path: Path) -> None:
    file_a = tmp_path / "src" / "a.py"
    file_b = tmp_path / "src" / "b.py"
    file_a.parent.mkdir(parents=True, exist_ok=True)
    file_a.write_text("def a():\n    pass\n", encoding="utf-8")
    file_b.write_text("def b():\n    pass\n", encoding="utf-8")

    runner, backend = _make_runner(tmp_path)
    batch = Batch(id=2, files=[str(file_a), str(file_b)])
    result = AnalysisResult(summary="batch fallback", key_insights=["ki"], raw_output="raw")

    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        BatchInteraction(
            prompt_payload={"file_content": "a", "language": "en"},
            raw_response="raw",
            analysis=StructuredAnalysisOutput(
                summary="A summary", key_insights=["k1"], language="en"
            ),
        ),
        BatchInteraction(
            prompt_payload={"file_content": "b", "language": "en"},
            raw_response="raw",
            analysis=StructuredAnalysisOutput(
                summary="B summary", key_insights=["k2"], language="en"
            ),
        ),
    ]

    with patch("lantern_cli.core.runner.StructuredAnalyzer", return_value=analyzer):
        runner._generate_bottom_up_doc(batch, result)

    backend.get_llm.assert_called_once()
    analyzer.analyze_batch.assert_called_once()
    analyzer.analyze.assert_not_called()

    out_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up" / "src"
    doc_a = (out_dir / "a.py.md").read_text(encoding="utf-8")
    doc_b = (out_dir / "b.py.md").read_text(encoding="utf-8")
    assert "A summary" in doc_a
    assert "B summary" in doc_b
    assert "## Key Insights" in doc_a


def test_generate_bottom_up_doc_fallbacks_to_invoke_then_batch_result(tmp_path: Path) -> None:
    file_a = tmp_path / "src" / "a.py"
    file_b = tmp_path / "src" / "b.py"
    file_a.parent.mkdir(parents=True, exist_ok=True)
    file_a.write_text("def a():\n    pass\n", encoding="utf-8")
    file_b.write_text("def b():\n    pass\n", encoding="utf-8")

    runner, _ = _make_runner(tmp_path)
    batch = Batch(id=3, files=[str(file_a), str(file_b)])
    result = AnalysisResult(summary="batch fallback", key_insights=["ki"], raw_output="raw")

    analyzer = MagicMock()
    analyzer.analyze_batch.side_effect = RuntimeError("batch failed")
    analyzer.analyze.side_effect = [
        StructuredAnalysisOutput(summary="A single", key_insights=["one"], language="en"),
        RuntimeError("single failed"),
    ]

    with patch("lantern_cli.core.runner.StructuredAnalyzer", return_value=analyzer):
        runner._generate_bottom_up_doc(batch, result)

    out_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up" / "src"
    doc_a = (out_dir / "a.py.md").read_text(encoding="utf-8")
    doc_b = (out_dir / "b.py.md").read_text(encoding="utf-8")

    assert "A single" in doc_a
    assert "batch fallback" in doc_b
    assert "- ki" in doc_b
