"""Tests for StateManager."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lantern_cli.core.architect import Plan, Phase, Batch
from lantern_cli.core.state_manager import StateManager, ExecutionState


class TestStateManager:
    """Test StateManager class."""

    @pytest.fixture
    def state_manager(self, tmp_path: Path) -> StateManager:
        """Create a StateManager instance with a temp path."""
        # Mock .lantern directory within tmp_path
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir()
        return StateManager(root_path=tmp_path)

    def test_initial_state(self, state_manager: StateManager) -> None:
        """Test initial state creation."""
        state = state_manager.load_state()
        assert state.last_batch_id == 0
        assert state.completed_batches == []
        assert state.global_summary == ""

    def test_save_and_load_state(self, state_manager: StateManager) -> None:
        """Test saving and loading state."""
        state = state_manager.state
        state.last_batch_id = 5
        state.completed_batches = [1, 2, 3, 4, 5]
        state.global_summary = "Summary so far"
        
        state_manager.save_state()
        
        # Reload
        new_manager = StateManager(state_manager.root_path)
        loaded_state = new_manager.load_state()
        
        assert loaded_state.last_batch_id == 5
        assert loaded_state.completed_batches == [1, 2, 3, 4, 5]
        assert loaded_state.global_summary == "Summary so far"

    def test_update_batch_completion(self, state_manager: StateManager) -> None:
        """Test updating batch status."""
        state_manager.update_batch_status(batch_id=1, success=True)
        
        assert state_manager.state.last_batch_id == 1
        assert 1 in state_manager.state.completed_batches
        
        # Update with next batch
        state_manager.update_batch_status(batch_id=2, success=True)
        assert state_manager.state.last_batch_id == 2
        assert 2 in state_manager.state.completed_batches

    def test_update_global_summary(self, state_manager: StateManager) -> None:
        """Test updating global summary."""
        state_manager.update_global_summary("New summary")
        assert state_manager.state.global_summary == "New summary"
        
        # Verify persistence
        new_manager = StateManager(state_manager.root_path)
        assert new_manager.state.global_summary == "New summary"

    def test_is_batch_completed(self, state_manager: StateManager) -> None:
        """Test checking if batch is completed."""
        state_manager.update_batch_status(1, True)
        assert state_manager.is_batch_completed(1)
        assert not state_manager.is_batch_completed(2)

    def test_get_pending_batches(self, state_manager: StateManager) -> None:
        """Test filtering pending batches."""
        # Create a dummy plan
        batch1 = Batch(id=1, files=["a"])
        batch2 = Batch(id=2, files=["b"])
        batch3 = Batch(id=3, files=["c"])
        
        plan = Plan(phases=[
            Phase(id=1, batches=[batch1, batch2]),
            Phase(id=2, batches=[batch3])
        ])
        
        # Mark batch 1 as complete
        state_manager.update_batch_status(1, True)
        
        pending = state_manager.get_pending_batches(plan)
        
        assert len(pending) == 2
        assert pending[0].id == 2
        assert pending[1].id == 3
        assert batch1 not in pending
