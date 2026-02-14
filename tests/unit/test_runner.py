"""Tests for Runner - comprehensive test suite.

Consolidates tests from:
- test_runner_run_batch.py
- test_runner_bottom_up_batch.py
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.core.architect import Batch
from lantern_cli.core.runner import Runner
from lantern_cli.llm.structured import BatchInteraction, StructuredAnalysisOutput
from tests.fixtures import LLMMockFactory, StateManagerMockFactory


@pytest.fixture
def runner(mock_llm: MagicMock, mock_state_manager: MagicMock, tmp_path: Path) -> Runner:
    """Create a Runner instance for testing."""
    return Runner(
        root_path=tmp_path,
        llm=mock_llm,
        state_manager=mock_state_manager,
    )


class TestRunBatchLifecycle:
    """Test Runner.run_batch execution lifecycle."""

    def test_run_batch_success(
        self, runner: Runner, mock_state_manager: MagicMock
    ) -> None:
        """Test successful batch execution.

        Runner delegates LLM calls to StructuredAnalyzer via _generate_bottom_up_doc,
        so we patch that method and verify the lifecycle (success flag + state update).
        """
        batch = Batch(id=1, files=["file1.py"])

        with patch.object(runner, "_generate_bottom_up_doc", return_value=[]) as mock_bottom_up:
            success = runner.run_batch(batch, "Prompt")

        assert success is True
        mock_bottom_up.assert_called_once()
        mock_state_manager.update_batch_status.assert_called_with(1, success=True)

    def test_run_batch_failure_on_analysis_error(
        self, runner: Runner, mock_state_manager: MagicMock
    ) -> None:
        """Test batch failure handling when analysis raises an unrecoverable error."""
        batch = Batch(id=1, files=["file1.py"])

        with patch.object(
            runner, "_generate_bottom_up_doc", side_effect=RuntimeError("LLM API Error")
        ):
            success = runner.run_batch(batch, "Prompt")

        assert success is False
        mock_state_manager.update_batch_status.assert_called_with(1, success=False)

    def test_run_batch_failure_on_doc_generation_error(
        self, runner: Runner, mock_state_manager: MagicMock
    ) -> None:
        """Test batch failure when doc generation raises."""
        batch = Batch(id=1, files=["file1.py"])

        with patch.object(
            runner, "_generate_bottom_up_doc", side_effect=OSError("Disk full")
        ):
            success = runner.run_batch(batch, "Prompt")

        assert success is False
        mock_state_manager.update_batch_status.assert_called_with(1, success=False)

    def test_prepare_context_truncates(
        self, runner: Runner, mock_state_manager: MagicMock
    ) -> None:
        """Test that context is properly truncated to MAX_CONTEXT_LENGTH."""
        # Test with short summary
        context = runner._prepare_context()
        assert context == "Old Summary"

        # Test with long summary
        runner.state_manager.state.global_summary = "A" * 5000
        long_context = runner._prepare_context()
        assert len(long_context) == runner.MAX_CONTEXT_LENGTH


class TestResponseExtraction:
    """Test Runner._extract_response_content method."""

    def test_extract_string_content(self, runner: Runner) -> None:
        """Test extracting simple string content."""
        response = MagicMock(content="Test summary")
        result = runner._extract_response_content(response)
        assert result == "Test summary"

    def test_extract_list_content(self, runner: Runner) -> None:
        """Test extracting list content."""
        response = MagicMock(content=["Part 1", "Part 2"])
        result = runner._extract_response_content(response)
        assert result == "Part 1\nPart 2"

    def test_extract_fails_on_empty_response(self, runner: Runner) -> None:
        """Test extraction failure on empty response."""
        response = None
        with pytest.raises(ValueError, match="Empty response"):
            runner._extract_response_content(response)

    def test_extract_fails_on_empty_content(self, runner: Runner) -> None:
        """Test extraction failure on empty content."""
        response = MagicMock(content="")
        with pytest.raises(ValueError, match="empty"):
            runner._extract_response_content(response)

    def test_extract_fails_on_empty_list(self, runner: Runner) -> None:
        """Test extraction failure on empty list."""
        response = MagicMock(content=[])
        with pytest.raises(ValueError, match="empty"):
            runner._extract_response_content(response)


class TestBottomUpDocGeneration:
    """Test Runner._generate_bottom_up_doc with fallback mechanisms."""

    def test_generate_bottom_up_doc_batch_success(self, tmp_path: Path) -> None:
        """Test successful batch analysis for bottom-up docs.

        Uses centralized fixtures for cleaner setup.
        """
        file_a = tmp_path / "src" / "a.py"
        file_b = tmp_path / "src" / "b.py"
        file_a.parent.mkdir(parents=True, exist_ok=True)
        file_a.write_text("def a():\n    pass\n", encoding="utf-8")
        file_b.write_text("def b():\n    pass\n", encoding="utf-8")

        llm = LLMMockFactory.create_batch(
            ["# a.py", "# b.py"],
            has_metadata=True,
        )
        state_manager = StateManagerMockFactory.create()
        runner = Runner(root_path=tmp_path, llm=llm, state_manager=state_manager)

        batch = Batch(id=2, files=[str(file_a), str(file_b)])
        result = "batch fallback content"

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

        analyzer.analyze_batch.assert_called_once()

        # Verify markdown files generated
        out_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up" / "src"
        doc_a = (out_dir / "a.py.md").read_text(encoding="utf-8")
        doc_b = (out_dir / "b.py.md").read_text(encoding="utf-8")
        assert "A summary" in doc_a
        assert "B summary" in doc_b

    def test_generate_bottom_up_doc_fallback_on_none(self, tmp_path: Path) -> None:
        """Test fallback when structured analysis fails for all files.

        When analyze_batch raises an exception and per-file fallback also fails,
        all structured_results entries are None. The runner should still produce
        a fallback markdown with 'Analysis failed or not available.' message.
        """
        file_a = tmp_path / "src" / "a.py"
        file_a.parent.mkdir(parents=True, exist_ok=True)
        file_a.write_text("def a():\n    pass\n", encoding="utf-8")

        llm = LLMMockFactory.create_batch(["# a.py"], has_metadata=True)
        state_manager = StateManagerMockFactory.create()
        runner = Runner(root_path=tmp_path, llm=llm, state_manager=state_manager)

        batch = Batch(id=3, files=[str(file_a)])
        result = "unused fallback string"

        analyzer = MagicMock()
        # Both batch and single-file analysis fail
        analyzer.analyze_batch.side_effect = RuntimeError("Invalid json output")
        analyzer.analyze.side_effect = RuntimeError("Invalid json output")

        with patch("lantern_cli.core.runner.StructuredAnalyzer", return_value=analyzer):
            runner._generate_bottom_up_doc(batch, result)

        # Verify fallback markdown was generated with failure message
        out_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up" / "src"
        doc_a = (out_dir / "a.py.md").read_text(encoding="utf-8")
        assert "a.py" in doc_a
        assert "Analysis failed or not available." in doc_a
