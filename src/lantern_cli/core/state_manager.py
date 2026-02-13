"""State Manager for Lantern execution."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from lantern_cli.core.architect import Plan, Batch
from lantern_cli.backends.base import BackendAdapter
from lantern_cli.core.memory_manager import MemoryManager
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionState:
    """Represents the current state of execution."""
    last_batch_id: int = 0
    completed_batches: List[int] = field(default_factory=list)
    failed_batches: List[int] = field(default_factory=list)
    global_summary: str = ""


class StateManager:
    """Manages persistence of execution state."""

    STATE_FILE = "state.json"

    def __init__(self, root_path: Path, backend: Optional[BackendAdapter] = None) -> None:
        """Initialize StateManager.

        Args:
            root_path: Project root path.
            backend: Backend adapter for memory compression (optional).
        """
        self.root_path = root_path
        self.memory_manager = MemoryManager(backend)
        self.lantern_dir = root_path / ".lantern"
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
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return ExecutionState(**data)
            except (json.JSONDecodeError, OSError):
                # If corrupt, potentially return fresh state or backup
                # For now, return fresh
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

    def get_pending_batches(self, plan: Plan) -> List[Batch]:
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
