"""Git diff-based change tracking for incremental analysis.

Uses `git diff` to detect repository changes since the last analysis
and calculates the impact set (files needing re-analysis) by combining
diff results with the dependency graph.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from lantern_cli.static_analysis.dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class DiffResult:
    """Parsed result from `git diff --name-status`."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)  # (old_path, new_path)


@dataclass
class ImpactSet:
    """Set of files affected by repository changes."""

    reanalyze: set[str] = field(default_factory=set)
    remove: set[str] = field(default_factory=set)
    rename_map: dict[str, str] = field(default_factory=dict)  # old_path -> new_path
    reason: dict[str, str] = field(default_factory=dict)


class DiffTracker:
    """Tracks repository changes via git and calculates analysis impact."""

    # If more than this fraction of files changed, suggest full re-analysis.
    FULL_REANALYSIS_THRESHOLD = 0.5

    def __init__(self, repo_path: Path) -> None:
        """Initialize DiffTracker.

        Args:
            repo_path: Root directory of the git repository.
        """
        self.repo_path = repo_path

    def is_git_repo(self) -> bool:
        """Check whether the repo path is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_current_commit(self) -> str:
        """Return the current HEAD commit SHA.

        Returns:
            Full 40-character commit hash.

        Raises:
            RuntimeError: If the git command fails.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git rev-parse HEAD failed: {result.stderr.strip()}")
            return result.stdout.strip()
        except subprocess.SubprocessError as exc:
            raise RuntimeError(f"Failed to get current commit: {exc}") from exc

    def commit_exists(self, sha: str) -> bool:
        """Check whether a commit SHA exists in the repository history.

        Args:
            sha: Commit hash to verify.

        Returns:
            True if the commit exists, False otherwise.
        """
        try:
            result = subprocess.run(
                ["git", "cat-file", "-t", sha],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip() == "commit"
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_diff(self, base_sha: str) -> DiffResult:
        """Run ``git diff`` between *base_sha* and HEAD and parse the output.

        Uses ``-M`` to detect renames.

        Args:
            base_sha: Base commit SHA (e.g. stored from previous analysis).

        Returns:
            Parsed DiffResult with added/modified/deleted/renamed lists.

        Raises:
            RuntimeError: If the git command fails.
        """
        try:
            result = subprocess.run(
                ["git", "diff", f"{base_sha}..HEAD", "--name-status", "-M"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git diff failed: {result.stderr.strip()}")
            return self._parse_name_status(result.stdout)
        except subprocess.SubprocessError as exc:
            raise RuntimeError(f"Failed to run git diff: {exc}") from exc

    def calculate_impact(
        self,
        diff: DiffResult,
        dep_graph: DependencyGraph,
        file_manifest: dict[str, dict] | None = None,
    ) -> ImpactSet:
        """Combine a diff result with the dependency graph to compute the impact set.

        Strategy:
        - Added / modified files → re-analyze.
        - Deleted files → remove artefacts.
        - Renamed (100 % similar) → remap manifest only (no re-analysis).
        - Renamed (< 100 %) → re-analyze new path, remove old.
        - Level-1 reverse dependencies of changed files → re-analyze.

        Args:
            diff: Parsed git diff result.
            dep_graph: Current (rebuilt) dependency graph.
            file_manifest: Optional existing file manifest for filtering.

        Returns:
            ImpactSet describing what needs re-analysis and cleanup.
        """
        impact = ImpactSet()

        # --- Direct changes ---
        for f in diff.added:
            impact.reanalyze.add(f)
            impact.reason[f] = "added"

        for f in diff.modified:
            impact.reanalyze.add(f)
            impact.reason[f] = "modified"

        for f in diff.deleted:
            impact.remove.add(f)
            impact.reason[f] = "deleted"

        for old_path, new_path in diff.renamed:
            # Treat renames as delete old + add new for analysis purposes.
            # Pure renames (no content change) could be optimised later by
            # checking similarity score, but for correctness we re-analyse.
            impact.remove.add(old_path)
            impact.reanalyze.add(new_path)
            impact.rename_map[old_path] = new_path
            impact.reason[new_path] = f"renamed from {old_path}"

        # --- Level-1 reverse dependencies ---
        directly_changed = set(impact.reanalyze)
        for changed_file in directly_changed:
            rev_deps = dep_graph.reverse_dependencies.get(changed_file, set())
            for dep in rev_deps:
                if dep not in impact.reanalyze and dep not in impact.remove:
                    impact.reanalyze.add(dep)
                    impact.reason[dep] = f"depends on changed file {changed_file}"

        return impact

    def should_full_reanalyze(self, impact: ImpactSet, total_files: int) -> bool:
        """Check whether incremental analysis is worthwhile.

        If the impact set covers more than ``FULL_REANALYSIS_THRESHOLD`` of all
        files, a full re-analysis is recommended instead.

        Args:
            impact: Calculated impact set.
            total_files: Total number of files in the repository scope.

        Returns:
            True if full re-analysis is recommended.
        """
        if total_files == 0:
            return False
        return len(impact.reanalyze) > self.FULL_REANALYSIS_THRESHOLD * total_files

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_name_status(output: str) -> DiffResult:
        """Parse the output of ``git diff --name-status -M``.

        Each non-empty line has the format::

            <status>\\t<path>
            R<score>\\t<old_path>\\t<new_path>

        Args:
            output: Raw stdout from git diff.

        Returns:
            Parsed DiffResult.
        """
        result = DiffResult()
        for line in output.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                logger.warning(f"Skipping unparsable git diff line: {line!r}")
                continue

            status = parts[0]
            if status == "A":
                result.added.append(parts[1])
            elif status == "M":
                result.modified.append(parts[1])
            elif status == "D":
                result.deleted.append(parts[1])
            elif status.startswith("R"):
                # Rename: R100\told\tnew  or  R075\told\tnew
                if len(parts) >= 3:
                    result.renamed.append((parts[1], parts[2]))
                else:
                    logger.warning(f"Rename line missing new path: {line!r}")
            elif status.startswith("C"):
                # Copy: treat new path as added
                if len(parts) >= 3:
                    result.added.append(parts[2])
            else:
                logger.debug(f"Ignoring git diff status {status!r} for {parts[1:]}")

        return result
