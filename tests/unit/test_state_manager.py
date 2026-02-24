"""Tests for StateManager."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lantern_cli.core.architect import Batch, Phase, Plan
from lantern_cli.core.state_manager import StateManager


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
        """Test updating global summary uses MemoryManager."""
        # Mock MemoryManager on the instance
        with patch.object(state_manager.memory_manager, "update_summary") as mock_update:
            mock_update.return_value = "Compressed Summary"

            state_manager.update_global_summary("New batch content")

            # Verify MemoryManager was called with current state and new content
            mock_update.assert_called_with("", "New batch content")

            # Verify state was updated with result from MemoryManager
            assert state_manager.state.global_summary == "Compressed Summary"

            # Verify persistence
            # Note: We can't easily verify persistence with the mock in place for a new instance,
            # but we can verify save_state was called if we mocked it, or check the file.
            # Here we just check the in-memory state update which implies logic correctness.

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

        plan = Plan(phases=[Phase(id=1, batches=[batch1, batch2]), Phase(id=2, batches=[batch3])])

        # Mark batch 1 as complete
        state_manager.update_batch_status(1, True)

        pending = state_manager.get_pending_batches(plan)

        assert len(pending) == 2
        assert pending[0].id == 2
        assert pending[1].id == 3
        assert batch1 not in pending

    def test_load_state_with_schema_mismatch(self, tmp_path: Path) -> None:
        """Test that unknown fields are filtered out and valid fields are kept."""
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir()
        state_path = lantern_dir / "state.json"
        # Write state with an unexpected field
        state_path.write_text(
            json.dumps({"last_batch_id": 1, "unknown_field": "bad"}), encoding="utf-8"
        )
        sm = StateManager(root_path=tmp_path)
        assert sm.state.last_batch_id == 1  # Valid fields preserved


class TestStateManagerIncremental:
    """Tests for incremental tracking methods."""

    @pytest.fixture
    def state_manager(self, tmp_path: Path) -> StateManager:
        """Create a StateManager instance with a temp path."""
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir()
        return StateManager(root_path=tmp_path)

    def test_update_git_commit(self, state_manager: StateManager) -> None:
        """Test storing and persisting git commit SHA."""
        state_manager.update_git_commit("abc123def456")
        assert state_manager.state.git_commit_sha == "abc123def456"

        # Verify persistence
        new_sm = StateManager(state_manager.root_path)
        assert new_sm.state.git_commit_sha == "abc123def456"

    def test_update_file_manifest(self, state_manager: StateManager) -> None:
        """Test recording file analysis metadata."""
        state_manager.update_file_manifest("src/main.py", 1, "batch_0001.sense", "success")
        assert "src/main.py" in state_manager.state.file_manifest
        entry = state_manager.state.file_manifest["src/main.py"]
        assert entry["batch_id"] == 1
        assert entry["sense_file"] == "batch_0001.sense"
        assert entry["status"] == "success"

    def test_remove_from_manifest(self, state_manager: StateManager) -> None:
        """Test removing a file from the manifest."""
        state_manager.update_file_manifest("src/old.py", 1, "batch_0001.sense", "success")
        assert "src/old.py" in state_manager.state.file_manifest

        state_manager.remove_from_manifest("src/old.py")
        assert "src/old.py" not in state_manager.state.file_manifest

    def test_remove_from_manifest_missing_key(self, state_manager: StateManager) -> None:
        """Test removing a non-existent file is a no-op."""
        state_manager.remove_from_manifest("nonexistent.py")
        assert "nonexistent.py" not in state_manager.state.file_manifest

    def test_clean_stale_artefacts(self, state_manager: StateManager) -> None:
        """Test cleaning sense records and bottom-up docs for removed files."""
        root = state_manager.root_path

        # Set up manifest
        state_manager.update_file_manifest("src/old.py", 1, "batch_0001.sense", "success")
        state_manager.update_file_manifest("src/keep.py", 1, "batch_0001.sense", "success")

        # Create sense file
        sense_dir = root / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        sense_path = sense_dir / "batch_0001.sense"
        sense_path.write_text(
            json.dumps(
                [
                    {"file_path": "src/old.py", "analysis": {}},
                    {"file_path": "src/keep.py", "analysis": {}},
                ]
            ),
            encoding="utf-8",
        )

        # Create bottom-up doc
        bu_dir = root / ".lantern" / "output" / "en" / "bottom_up"
        bu_dir.mkdir(parents=True)
        md_path = bu_dir / "src" / "old.py.md"
        md_path.parent.mkdir(parents=True)
        md_path.write_text("# old.py", encoding="utf-8")

        state_manager.clean_stale_artefacts({"src/old.py"})

        # Manifest should no longer contain old.py
        assert "src/old.py" not in state_manager.state.file_manifest
        assert "src/keep.py" in state_manager.state.file_manifest

        # Sense file should only contain keep.py record
        with open(sense_path, encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 1
        assert records[0]["file_path"] == "src/keep.py"

        # Bottom-up doc should be removed
        assert not md_path.exists()

    def test_reset_for_incremental(self, state_manager: StateManager) -> None:
        """Test resetting batch IDs for re-execution."""
        state_manager.update_batch_status(1, True)
        state_manager.update_batch_status(2, True)
        state_manager.update_batch_status(3, False)

        assert 1 in state_manager.state.completed_batches
        assert 3 in state_manager.state.failed_batches

        state_manager.reset_for_incremental([1, 3])

        assert 1 not in state_manager.state.completed_batches
        assert 3 not in state_manager.state.failed_batches
        assert 2 in state_manager.state.completed_batches

    def test_output_dir_parameter(self, tmp_path: Path) -> None:
        """Test that output_dir parameter changes the state directory."""
        custom_dir = tmp_path / "custom_output"
        custom_dir.mkdir()
        sm = StateManager(root_path=tmp_path, output_dir="custom_output")
        assert sm.lantern_dir == tmp_path / "custom_output"
