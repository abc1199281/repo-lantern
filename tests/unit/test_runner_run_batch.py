"""Tests for Runner.run_batch lifecycle."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.backends.base import AnalysisResult
from lantern_cli.core.architect import Batch
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import ExecutionState


@pytest.fixture
def mock_backend() -> MagicMock:
    backend = MagicMock()
    backend.summarize_batch.return_value = AnalysisResult(
        summary="Test Summary",
        key_insights=["Insight 1"],
        raw_output="Raw",
    )
    backend.get_llm.return_value = MagicMock()
    return backend


@pytest.fixture
def mock_state_manager() -> MagicMock:
    state_manager = MagicMock()
    state_manager.state = ExecutionState(global_summary="Old Summary")
    return state_manager


@pytest.fixture
def runner(mock_backend: MagicMock, mock_state_manager: MagicMock, tmp_path: Path) -> Runner:
    return Runner(root_path=tmp_path, backend=mock_backend, state_manager=mock_state_manager)


def test_run_batch_success(
    runner: Runner, mock_backend: MagicMock, mock_state_manager: MagicMock
) -> None:
    batch = Batch(id=1, files=["file1.py"])

    with patch.object(runner, "_generate_bottom_up_doc") as mock_bottom_up:
        success = runner.run_batch(batch, "Prompt")

    assert success is True
    mock_backend.summarize_batch.assert_called_once()
    args = mock_backend.summarize_batch.call_args
    assert args.kwargs["context"] == "Old Summary"
    mock_bottom_up.assert_called_once()
    mock_state_manager.update_global_summary.assert_called_with("Batch 1 Summary:\nTest Summary")
    mock_state_manager.update_batch_status.assert_called_with(1, success=True)


def test_run_batch_failure(
    runner: Runner, mock_backend: MagicMock, mock_state_manager: MagicMock
) -> None:
    batch = Batch(id=1, files=["file1.py"])
    mock_backend.summarize_batch.side_effect = Exception("API Error")

    success = runner.run_batch(batch, "Prompt")

    assert success is False
    mock_state_manager.update_batch_status.assert_called_with(1, success=False)


def test_prepare_context_truncates(runner: Runner) -> None:
    context = runner._prepare_context()
    assert context == "Old Summary"

    runner.state_manager.state.global_summary = "A" * 5000
    long_context = runner._prepare_context()
    assert len(long_context) == runner.MAX_CONTEXT_LENGTH
