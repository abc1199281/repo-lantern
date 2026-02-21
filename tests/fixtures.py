"""Shared test fixtures and factories for repo-lantern tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lantern_cli.core.state_manager import ExecutionState
from lantern_cli.llm.backend import LLMResponse


class BackendMockFactory:
    """Factory for creating consistent Backend mocks across tests."""

    @staticmethod
    def create(
        content: str = "Test Summary",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> MagicMock:
        """Create a mock Backend with optional usage metadata.

        Args:
            content: Response content text.
            input_tokens: Optional input token count for usage_metadata.
            output_tokens: Optional output token count for usage_metadata.

        Returns:
            Configured MagicMock Backend instance.
        """
        backend = MagicMock()

        usage = None
        if input_tokens is not None or output_tokens is not None:
            usage = {
                "input_tokens": input_tokens or 0,
                "output_tokens": output_tokens or 0,
            }

        response = LLMResponse(content=content, usage_metadata=usage)
        backend.invoke.return_value = response
        backend.model_name = "test-model"
        return backend

    @staticmethod
    def create_batch(
        responses: list[str],
        has_metadata: bool = False,
    ) -> MagicMock:
        """Create a mock Backend for batch operations.

        Args:
            responses: List of response content strings.
            has_metadata: Whether to add usage_metadata to responses.

        Returns:
            Configured MagicMock Backend instance.
        """
        backend = MagicMock()

        # Create LLMResponse mocks for invoke
        response_list = []
        for content in responses:
            usage = {"input_tokens": 100, "output_tokens": 50} if has_metadata else None
            response_list.append(LLMResponse(content=content, usage_metadata=usage))

        backend.invoke.side_effect = response_list
        backend.model_name = "test-model"
        return backend

    @staticmethod
    def create_failing() -> MagicMock:
        """Create a mock Backend that fails on invoke.

        Returns:
            Configured MagicMock Backend instance that raises Exception.
        """
        backend = MagicMock()
        backend.invoke.side_effect = Exception("LLM API Error")
        backend.model_name = "test-model"
        return backend


# Keep backward-compatible alias
LLMMockFactory = BackendMockFactory


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
def mock_backend() -> MagicMock:
    """Fixture: Standard Backend mock."""
    return BackendMockFactory.create()


@pytest.fixture
def mock_backend_with_metadata() -> MagicMock:
    """Fixture: Backend mock with usage_metadata."""
    return BackendMockFactory.create(
        content="Test Summary",
        input_tokens=100,
        output_tokens=50,
    )


@pytest.fixture
def mock_backend_failing() -> MagicMock:
    """Fixture: Backend mock that fails."""
    return BackendMockFactory.create_failing()


# Backward-compatible fixtures
@pytest.fixture
def mock_llm() -> MagicMock:
    """Fixture: Standard Backend mock (legacy name)."""
    return BackendMockFactory.create()


@pytest.fixture
def mock_llm_with_metadata() -> MagicMock:
    """Fixture: Backend mock with usage_metadata (legacy name)."""
    return BackendMockFactory.create(
        content="Test Summary",
        input_tokens=100,
        output_tokens=50,
    )


@pytest.fixture
def mock_llm_failing() -> MagicMock:
    """Fixture: Backend mock that fails (legacy name)."""
    return BackendMockFactory.create_failing()


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
