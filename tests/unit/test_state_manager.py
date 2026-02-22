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


class TestStateManagerIncremental:
    """Test incremental tracking helpers."""

    @pytest.fixture
    def state_manager(self, tmp_path: Path) -> StateManager:
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir()
        return StateManager(root_path=tmp_path)

    def test_initial_state_has_new_fields(self, state_manager: StateManager) -> None:
        """New fields default to empty."""
        assert state_manager.state.git_commit_sha == ""
        assert state_manager.state.file_manifest == {}

    def test_update_git_commit(self, state_manager: StateManager) -> None:
        state_manager.update_git_commit("abc123")
        assert state_manager.state.git_commit_sha == "abc123"

        # Verify persistence
        reloaded = StateManager(state_manager.root_path)
        assert reloaded.state.git_commit_sha == "abc123"

    def test_update_file_manifest(self, state_manager: StateManager) -> None:
        state_manager.update_file_manifest("src/main.py", 1, "batch_0001.sense", "success")
        state_manager.save_state()

        entry = state_manager.state.file_manifest["src/main.py"]
        assert entry["batch_id"] == 1
        assert entry["sense_file"] == "batch_0001.sense"
        assert entry["status"] == "success"

    def test_remove_from_manifest(self, state_manager: StateManager) -> None:
        state_manager.update_file_manifest("src/old.py", 1, "batch_0001.sense", "success")
        state_manager.remove_from_manifest("src/old.py")
        assert "src/old.py" not in state_manager.state.file_manifest

    def test_remove_from_manifest_nonexistent(self, state_manager: StateManager) -> None:
        """Removing a key that doesn't exist should not raise."""
        state_manager.remove_from_manifest("nonexistent.py")

    def test_clean_stale_artefacts_removes_sense_records(self, tmp_path: Path) -> None:
        sm = StateManager(root_path=tmp_path)
        sm.update_file_manifest("src/old.py", 1, "batch_0001.sense", "success")
        sm.update_file_manifest("src/keep.py", 1, "batch_0001.sense", "success")
        sm.save_state()

        # Create a .sense file with both records
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        sense_file = sense_dir / "batch_0001.sense"
        records = [
            {"file_path": "src/old.py", "analysis": {"summary": "old"}},
            {"file_path": "src/keep.py", "analysis": {"summary": "keep"}},
        ]
        with open(sense_file, "w") as f:
            json.dump(records, f)

        sm.clean_stale_artefacts({"src/old.py"})

        # Verify sense file was rewritten without the removed record
        with open(sense_file) as f:
            remaining = json.load(f)
        assert len(remaining) == 1
        assert remaining[0]["file_path"] == "src/keep.py"

        # Verify manifest updated
        assert "src/old.py" not in sm.state.file_manifest
        assert "src/keep.py" in sm.state.file_manifest

    def test_clean_stale_artefacts_removes_bottom_up_md(self, tmp_path: Path) -> None:
        sm = StateManager(root_path=tmp_path)
        sm.update_file_manifest("src/old.py", 1, "batch_0001.sense", "success")
        sm.save_state()

        # Create bottom-up markdown
        bu_dir = tmp_path / ".lantern" / "output" / "en" / "bottom_up" / "src"
        bu_dir.mkdir(parents=True)
        md_file = bu_dir / "old.py.md"
        md_file.write_text("# old.py\nanalysis...\n")

        # Create empty sense dir so clean doesn't error
        (tmp_path / ".lantern" / "sense").mkdir(parents=True, exist_ok=True)

        sm.clean_stale_artefacts({"src/old.py"})

        assert not md_file.exists()

    def test_reset_for_incremental(self, state_manager: StateManager) -> None:
        state_manager.update_batch_status(1, True)
        state_manager.update_batch_status(2, True)
        state_manager.update_batch_status(3, True)

        state_manager.reset_for_incremental([2, 3])

        assert 1 in state_manager.state.completed_batches
        assert 2 not in state_manager.state.completed_batches
        assert 3 not in state_manager.state.completed_batches

    def test_save_and_load_with_new_fields(self, state_manager: StateManager) -> None:
        """Verify round-trip with git_commit_sha and file_manifest."""
        state_manager.state.git_commit_sha = "deadbeef"
        state_manager.state.file_manifest = {
            "src/a.py": {"batch_id": 1, "sense_file": "batch_0001.sense", "status": "success"}
        }
        state_manager.save_state()

        reloaded = StateManager(state_manager.root_path)
        assert reloaded.state.git_commit_sha == "deadbeef"
        assert "src/a.py" in reloaded.state.file_manifest
        assert reloaded.state.file_manifest["src/a.py"]["batch_id"] == 1

    def test_load_old_state_without_new_fields(self, tmp_path: Path) -> None:
        """Loading state.json that lacks new fields should not crash."""
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir()
        state_path = lantern_dir / "state.json"
        # Old-format state (no git_commit_sha / file_manifest)
        old_state = {
            "last_batch_id": 3,
            "completed_batches": [1, 2, 3],
            "failed_batches": [],
            "global_summary": "old summary",
        }
        with open(state_path, "w") as f:
            json.dump(old_state, f)

        sm = StateManager(root_path=tmp_path)
        assert sm.state.last_batch_id == 3
        assert sm.state.git_commit_sha == ""
        assert sm.state.file_manifest == {}
