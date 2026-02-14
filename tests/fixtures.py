"""Shared test fixtures and factories for lantern-cli tests."""

from pathlib import Path
from unittest.mock import MagicMock
from typing import Optional, Dict, Any

import pytest

from lantern_cli.core.state_manager import ExecutionState


class LLMMockFactory:
    """Factory for creating consistent LLM mocks across tests."""

    @staticmethod
    def create(
        content: str = "Test Summary",
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> MagicMock:
        """Create a mock LLM with optional usage metadata.

        Args:
            content: Response content text.
            input_tokens: Optional input token count for usage_metadata.
            output_tokens: Optional output token count for usage_metadata.

        Returns:
            Configured MagicMock LLM instance.
        """
        llm = MagicMock()
        response = MagicMock(content=content)

        # Add usage_metadata if tokens provided
        if input_tokens is not None or output_tokens is not None:
            response.usage_metadata = {
                "input_tokens": input_tokens or 0,
                "output_tokens": output_tokens or 0,
            }

        llm.invoke.return_value = response
        return llm

    @staticmethod
    def create_batch(
        responses: list[str],
        has_metadata: bool = False,
    ) -> MagicMock:
        """Create a mock LLM for batch operations.

        Args:
            responses: List of response content strings.
            has_metadata: Whether to add usage_metadata to responses.

        Returns:
            Configured MagicMock LLM instance.
        """
        llm = MagicMock()

        # Create response mocks
        response_mocks = []
        for content in responses:
            response = MagicMock(content=content)
            if has_metadata:
                response.usage_metadata = {
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            response_mocks.append(response)

        llm.invoke.side_effect = response_mocks
        return llm

    @staticmethod
    def create_failing() -> MagicMock:
        """Create a mock LLM that fails on invoke.

        Returns:
            Configured MagicMock LLM instance that raises Exception.
        """
        llm = MagicMock()
        llm.invoke.side_effect = Exception("LLM API Error")
        return llm


class StateManagerMockFactory:
    """Factory for creating consistent StateManager mocks across tests."""

    @staticmethod
    def create(
        global_summary: str = "Old Summary",
    ) -> MagicMock:
        """Create a mock StateManager.

        Args:
            global_summary: Initial global summary text.

        Returns:
            Configured MagicMock StateManager instance.
        """
        state_manager = MagicMock()
        state_manager.state = ExecutionState(global_summary=global_summary)
        return state_manager


# Pytest fixtures using factories

@pytest.fixture
def mock_llm() -> MagicMock:
    """Fixture: Standard LLM mock."""
    return LLMMockFactory.create()


@pytest.fixture
def mock_llm_with_metadata() -> MagicMock:
    """Fixture: LLM mock with usage_metadata."""
    return LLMMockFactory.create(
        content="Test Summary",
        input_tokens=100,
        output_tokens=50,
    )


@pytest.fixture
def mock_llm_failing() -> MagicMock:
    """Fixture: LLM mock that fails."""
    return LLMMockFactory.create_failing()


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Fixture: Standard StateManager mock."""
    return StateManagerMockFactory.create()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Fixture: Create minimal project structure in tmp_path.

    Returns:
        Project root path with .lantern directory.
    """
    lantern_dir = tmp_path / ".lantern"
    lantern_dir.mkdir(parents=True, exist_ok=True)

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    # Create sample files
    (src_dir / "main.py").write_text("def main():\n    pass\n")
    (src_dir / "utils.py").write_text("def util():\n    pass\n")

    return tmp_path
