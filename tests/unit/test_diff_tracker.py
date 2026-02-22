"""Tests for DiffTracker."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lantern_cli.core.diff_tracker import DiffResult, DiffTracker, ImpactSet
from lantern_cli.static_analysis.dependency_graph import DependencyGraph


class TestParseNameStatus:
    """Test DiffTracker._parse_name_status static method."""

    def test_empty_output(self) -> None:
        result = DiffTracker._parse_name_status("")
        assert result.added == []
        assert result.modified == []
        assert result.deleted == []
        assert result.renamed == []

    def test_added_files(self) -> None:
        output = "A\tsrc/new_file.py\nA\tsrc/another.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.added == ["src/new_file.py", "src/another.py"]

    def test_modified_files(self) -> None:
        output = "M\tsrc/main.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.modified == ["src/main.py"]

    def test_deleted_files(self) -> None:
        output = "D\tsrc/old.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.deleted == ["src/old.py"]

    def test_renamed_files(self) -> None:
        output = "R100\tsrc/old.py\tsrc/new.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.renamed == [("src/old.py", "src/new.py")]

    def test_renamed_with_similarity_score(self) -> None:
        output = "R075\tsrc/old.py\tsrc/new.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.renamed == [("src/old.py", "src/new.py")]

    def test_copy_treated_as_added(self) -> None:
        output = "C100\tsrc/original.py\tsrc/copy.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.added == ["src/copy.py"]

    def test_mixed_statuses(self) -> None:
        output = (
            "A\tsrc/new.py\n"
            "M\tsrc/main.py\n"
            "D\tsrc/old.py\n"
            "R100\tsrc/before.py\tsrc/after.py\n"
        )
        result = DiffTracker._parse_name_status(output)
        assert result.added == ["src/new.py"]
        assert result.modified == ["src/main.py"]
        assert result.deleted == ["src/old.py"]
        assert result.renamed == [("src/before.py", "src/after.py")]

    def test_unparsable_line_skipped(self) -> None:
        output = "badline\nM\tsrc/main.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.modified == ["src/main.py"]

    def test_rename_missing_new_path(self) -> None:
        output = "R100\tsrc/old.py\n"
        result = DiffTracker._parse_name_status(output)
        assert result.renamed == []


class TestCalculateImpact:
    """Test DiffTracker.calculate_impact."""

    @pytest.fixture
    def tracker(self, tmp_path: Path) -> DiffTracker:
        return DiffTracker(tmp_path)

    @pytest.fixture
    def dep_graph(self, tmp_path: Path) -> DependencyGraph:
        """Create a mock dependency graph with known relationships."""
        mock_filter = MagicMock()
        mock_filter.walk.return_value = []
        graph = DependencyGraph(tmp_path, file_filter=mock_filter)
        # Manually set up dependencies:
        # main.py -> utils.py -> helpers.py
        graph.dependencies["src/main.py"] = {"src/utils.py"}
        graph.dependencies["src/utils.py"] = {"src/helpers.py"}
        graph.dependencies["src/helpers.py"] = set()
        graph.dependencies["src/standalone.py"] = set()
        graph.reverse_dependencies["src/utils.py"] = {"src/main.py"}
        graph.reverse_dependencies["src/helpers.py"] = {"src/utils.py"}
        return graph

    def test_added_file_in_impact(self, tracker: DiffTracker, dep_graph: DependencyGraph) -> None:
        diff = DiffResult(added=["src/new.py"])
        impact = tracker.calculate_impact(diff, dep_graph)
        assert "src/new.py" in impact.reanalyze
        assert impact.reason["src/new.py"] == "added"

    def test_modified_file_in_impact(
        self, tracker: DiffTracker, dep_graph: DependencyGraph
    ) -> None:
        diff = DiffResult(modified=["src/helpers.py"])
        impact = tracker.calculate_impact(diff, dep_graph)
        assert "src/helpers.py" in impact.reanalyze
        # Level-1 reverse dep: utils.py depends on helpers.py
        assert "src/utils.py" in impact.reanalyze
        # Level-2: main.py depends on utils.py — should NOT be included
        assert "src/main.py" not in impact.reanalyze

    def test_deleted_file_in_remove(self, tracker: DiffTracker, dep_graph: DependencyGraph) -> None:
        diff = DiffResult(deleted=["src/old.py"])
        impact = tracker.calculate_impact(diff, dep_graph)
        assert "src/old.py" in impact.remove
        assert "src/old.py" not in impact.reanalyze

    def test_renamed_file_handling(self, tracker: DiffTracker, dep_graph: DependencyGraph) -> None:
        diff = DiffResult(renamed=[("src/old.py", "src/new.py")])
        impact = tracker.calculate_impact(diff, dep_graph)
        assert "src/old.py" in impact.remove
        assert "src/new.py" in impact.reanalyze
        assert impact.rename_map["src/old.py"] == "src/new.py"

    def test_level1_reverse_deps_included(
        self, tracker: DiffTracker, dep_graph: DependencyGraph
    ) -> None:
        diff = DiffResult(modified=["src/utils.py"])
        impact = tracker.calculate_impact(diff, dep_graph)
        # Direct change
        assert "src/utils.py" in impact.reanalyze
        # Level-1 reverse dep
        assert "src/main.py" in impact.reanalyze
        assert impact.reason["src/main.py"] == "depends on changed file src/utils.py"

    def test_standalone_file_no_cascade(
        self, tracker: DiffTracker, dep_graph: DependencyGraph
    ) -> None:
        diff = DiffResult(modified=["src/standalone.py"])
        impact = tracker.calculate_impact(diff, dep_graph)
        assert impact.reanalyze == {"src/standalone.py"}

    def test_empty_diff(self, tracker: DiffTracker, dep_graph: DependencyGraph) -> None:
        diff = DiffResult()
        impact = tracker.calculate_impact(diff, dep_graph)
        assert impact.reanalyze == set()
        assert impact.remove == set()


class TestShouldFullReanalyze:
    """Test DiffTracker.should_full_reanalyze."""

    def test_below_threshold(self, tmp_path: Path) -> None:
        tracker = DiffTracker(tmp_path)
        impact = ImpactSet(reanalyze={"a.py", "b.py"})
        assert not tracker.should_full_reanalyze(impact, total_files=10)

    def test_above_threshold(self, tmp_path: Path) -> None:
        tracker = DiffTracker(tmp_path)
        impact = ImpactSet(reanalyze={f"{i}.py" for i in range(6)})
        assert tracker.should_full_reanalyze(impact, total_files=10)

    def test_zero_total_files(self, tmp_path: Path) -> None:
        tracker = DiffTracker(tmp_path)
        impact = ImpactSet(reanalyze={"a.py"})
        assert not tracker.should_full_reanalyze(impact, total_files=0)


class TestGitOperations:
    """Test git-related methods with subprocess mocking."""

    @pytest.fixture
    def tracker(self, tmp_path: Path) -> DiffTracker:
        return DiffTracker(tmp_path)

    def test_is_git_repo_true(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
            assert tracker.is_git_repo() is True

    def test_is_git_repo_false(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            assert tracker.is_git_repo() is False

    def test_is_git_repo_command_not_found(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert tracker.is_git_repo() is False

    def test_get_current_commit(self, tracker: DiffTracker) -> None:
        sha = "abc123def456" * 3 + "abcd"  # 40 chars
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=f"{sha}\n")
            assert tracker.get_current_commit() == sha

    def test_get_current_commit_failure(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stderr="fatal: error")
            with pytest.raises(RuntimeError, match="git rev-parse HEAD failed"):
                tracker.get_current_commit()

    def test_commit_exists_true(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="commit\n")
            assert tracker.commit_exists("abc123") is True

    def test_commit_exists_false(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert tracker.commit_exists("nonexistent") is False

    def test_get_diff(self, tracker: DiffTracker) -> None:
        diff_output = "M\tsrc/main.py\nA\tsrc/new.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=diff_output)
            result = tracker.get_diff("abc123")
            assert result.modified == ["src/main.py"]
            assert result.added == ["src/new.py"]

    def test_get_diff_failure(self, tracker: DiffTracker) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stderr="fatal: bad object")
            with pytest.raises(RuntimeError, match="git diff failed"):
                tracker.get_diff("badsha")
