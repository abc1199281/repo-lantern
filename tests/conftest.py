"""Pytest configuration and shared fixtures for repo-lantern tests."""

# Import all fixtures from fixtures module to make them available globally
from tests.fixtures import (
    BackendMockFactory,
    LLMMockFactory,
    StateManagerMockFactory,
    mock_backend,
    mock_backend_failing,
    mock_backend_with_metadata,
    mock_llm,
    mock_llm_failing,
    mock_llm_with_metadata,
    mock_state_manager,
    tmp_project,
)

__all__ = [
    "mock_backend",
    "mock_backend_with_metadata",
    "mock_backend_failing",
    "mock_llm",
    "mock_llm_with_metadata",
    "mock_llm_failing",
    "mock_state_manager",
    "tmp_project",
    "BackendMockFactory",
    "LLMMockFactory",
    "StateManagerMockFactory",
]
