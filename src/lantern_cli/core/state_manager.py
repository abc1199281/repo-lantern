"""State Manager for Lantern execution."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from lantern_cli.core.architect import Batch, Plan
from lantern_cli.core.memory_manager import MemoryManager

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)


@dataclass
class ExecutionState:
    """Represents the current state of execution."""

    last_batch_id: int = 0
    completed_batches: list[int] = field(default_factory=list)
    failed_batches: list[int] = field(default_factory=list)
    global_summary: str = ""
    git_commit_sha: str = ""
    file_manifest: dict[str, dict[str, Any]] = field(default_factory=dict)


class StateManager:
    """Manages persistence of execution state."""

    STATE_FILE = "state.json"

    def __init__(
        self,
        root_path: Path,
        backend: Optional["Backend"] = None,
        output_dir: str | None = None,
    ) -> None:
        """Initialize StateManager.

        Args:
            root_path: Project root path.
            backend: Backend instance for memory compression (optional).
            output_dir: Custom output directory name (default: ".lantern").
        """
        self.root_path = root_path
        self.memory_manager = MemoryManager(backend)
        base_out = output_dir or ".lantern"
        self.lantern_dir = root_path / base_out
        self.state_path = self.lantern_dir / self.STATE_FILE
        self.state: ExecutionState = self.load_state()

    def load_state(self) -> ExecutionState:
        """Load state from file or create default."""
        if not self.lantern_dir.exists():
            try:
                self.lantern_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create lantern directory: {e}")

        if self.state_path.exists():
            try:
                with open(self.state_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return ExecutionState(**data)
            except (json.JSONDecodeError, OSError, TypeError):
                # If corrupt or schema mismatch, return fresh state
                pass

        return ExecutionState()

    def save_state(self) -> None:
        """Save current state to file."""
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.state), f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save state to {self.state_path}: {e}")

    def update_batch_status(self, batch_id: int, success: bool) -> None:
        """Update status of a batch execution.

        Args:
            batch_id: Batch ID.
            success: Whether execution was successful.
        """
        if success:
            if batch_id not in self.state.completed_batches:
                self.state.completed_batches.append(batch_id)
                self.state.completed_batches.sort()

            # Update last_batch_id if this is higher
            if batch_id > self.state.last_batch_id:
                self.state.last_batch_id = batch_id

            # Remove from failed if it was there
            if batch_id in self.state.failed_batches:
                self.state.failed_batches.remove(batch_id)
        else:
            if batch_id not in self.state.failed_batches:
                self.state.failed_batches.append(batch_id)

        self.save_state()

    def update_global_summary(self, new_content: str) -> None:
        """Update global summary with new content using MemoryManager.

        Args:
            new_content: New content to append (e.g., batch summary).
        """
        current = self.state.global_summary
        updated = self.memory_manager.update_summary(current, new_content)
        self.state.global_summary = updated
        self.save_state()

    def is_batch_completed(self, batch_id: int) -> bool:
        """Check if a batch has been successfully completed.

        Args:
            batch_id: Batch ID.

        Returns:
            True if completed, False otherwise.
        """
        return batch_id in self.state.completed_batches

    def get_pending_batches(self, plan: Plan) -> list[Batch]:
        """Get list of batches that need to be executed.

        Args:
            plan: The analysis plan.

        Returns:
            List of pending batches.
        """
        pending = []
        for phase in plan.phases:
            for batch in phase.batches:
                if not self.is_batch_completed(batch.id):
                    pending.append(batch)
        return pending

    # ------------------------------------------------------------------
    # Incremental tracking helpers
    # ------------------------------------------------------------------

    def update_git_commit(self, sha: str) -> None:
        """Store the git commit SHA for the current analysis snapshot.

        Args:
            sha: Full commit hash.
        """
        self.state.git_commit_sha = sha
        self.save_state()

    def update_file_manifest(
        self, file_path: str, batch_id: int, sense_file: str, status: str
    ) -> None:
        """Record a file's analysis metadata in the manifest.

        Args:
            file_path: Relative file path within the repository.
            batch_id: Batch ID that processed this file.
            sense_file: Name of the .sense file containing the analysis.
            status: Analysis status (``success``, ``empty``, ``error``).
        """
        self.state.file_manifest[file_path] = {
            "batch_id": batch_id,
            "sense_file": sense_file,
            "status": status,
        }
        # Defer save — caller should call save_state() after bulk updates.

    def remove_from_manifest(self, file_path: str) -> None:
        """Remove a file from the manifest (e.g. after deletion).

        Args:
            file_path: Relative file path to remove.
        """
        self.state.file_manifest.pop(file_path, None)

    def clean_stale_artefacts(
        self,
        files_to_remove: set[str],
        output_dir: str | None = None,
    ) -> None:
        """Delete .sense records and bottom-up docs for removed/stale files.

        Args:
            files_to_remove: Set of relative file paths whose artefacts should
                be cleaned.
            output_dir: Custom output directory name (default: ".lantern").
        """
        base_out = output_dir or ".lantern"
        sense_dir = self.root_path / base_out / "sense"
        bottom_up_dir = self.root_path / base_out / "output"

        # Collect batch IDs whose .sense files need rewriting.
        affected_batches: dict[int, str] = {}  # batch_id -> sense_file
        for fp in files_to_remove:
            entry = self.state.file_manifest.get(fp)
            if entry:
                affected_batches[entry["batch_id"]] = entry["sense_file"]
            self.remove_from_manifest(fp)

        # Rewrite each affected .sense file, filtering out removed file records.
        for _batch_id, sense_name in affected_batches.items():
            sense_path = sense_dir / sense_name
            if not sense_path.exists():
                continue
            try:
                with open(sense_path, encoding="utf-8") as f:
                    records = json.load(f)
                if isinstance(records, list):
                    records = [r for r in records if r.get("file_path") not in files_to_remove]
                    with open(sense_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Failed to clean sense file {sense_path}: {exc}")

        # Remove bottom-up markdown files for all languages.
        if bottom_up_dir.exists():
            for lang_dir in bottom_up_dir.iterdir():
                bu_dir = lang_dir / "bottom_up" if lang_dir.is_dir() else None
                if bu_dir and bu_dir.exists():
                    for fp in files_to_remove:
                        md_path = bu_dir / fp
                        md_with_ext = bu_dir / f"{fp}.md"
                        for p in (md_path, md_with_ext):
                            if p.exists():
                                try:
                                    p.unlink()
                                except OSError as exc:
                                    logger.warning(f"Failed to remove {p}: {exc}")

        self.save_state()

    def reset_for_incremental(self, batches_to_rerun: list[int]) -> None:
        """Remove batch IDs from completed list so they can be re-executed.

        Args:
            batches_to_rerun: List of batch IDs that need re-execution.
        """
        for bid in batches_to_rerun:
            if bid in self.state.completed_batches:
                self.state.completed_batches.remove(bid)
            if bid in self.state.failed_batches:
                self.state.failed_batches.remove(bid)
        self.save_state()
