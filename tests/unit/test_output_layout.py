"""Tests for output_layout utilities."""

from pathlib import Path

import pytest

from lantern_cli.core.architect import Batch, Phase, Plan
from lantern_cli.core.output_layout import (
    SYNTHESIS_OFFSET,
    FlatFileEntry,
    build_manifest,
    compute_file_number,
    compute_flat_filename,
    create_backward_compat_symlinks,
    generate_guide_md,
    inject_navigation,
    inject_navigation_all_files,
    rel_path_to_flat_stem,
)


@pytest.fixture
def simple_plan() -> Plan:
    return Plan(
        phases=[
            Phase(
                id=0,
                batches=[
                    Batch(id=1, files=["src/config/loader.py", "src/llm/backend.py"]),
                    Batch(id=2, files=["src/llm/factory.py"]),
                ],
                learning_objectives=["Understand config and LLM basics"],
            ),
            Phase(
                id=1,
                batches=[
                    Batch(id=3, files=["src/core/runner.py", "src/core/architect.py"]),
                ],
                learning_objectives=["Understand core orchestration"],
            ),
        ],
    )


class TestRelPathToFlatStem:
    def test_simple_path(self) -> None:
        assert rel_path_to_flat_stem("src/core/runner.py") == "src--core--runner.py"

    def test_single_component(self) -> None:
        assert rel_path_to_flat_stem("main.py") == "main.py"

    def test_deep_path(self) -> None:
        assert rel_path_to_flat_stem("src/a/b/c/d.py") == "src--a--b--c--d.py"


class TestComputeFlatFilename:
    def test_single_digit(self) -> None:
        assert compute_flat_filename(4, "src--core--runner.py") == "04-src--core--runner.py.md"

    def test_double_digit(self) -> None:
        assert compute_flat_filename(12, "src--main.py") == "12-src--main.py.md"

    def test_triple_digit(self) -> None:
        assert compute_flat_filename(100, "src--main.py") == "100-src--main.py.md"


class TestComputeFileNumber:
    def test_first_file_in_first_batch(self, simple_plan: Plan) -> None:
        assert compute_file_number(1, 0, simple_plan) == SYNTHESIS_OFFSET + 1

    def test_second_file_in_first_batch(self, simple_plan: Plan) -> None:
        assert compute_file_number(1, 1, simple_plan) == SYNTHESIS_OFFSET + 2

    def test_first_file_in_second_batch(self, simple_plan: Plan) -> None:
        # Batch 1 has 2 files, so batch 2 starts at offset + 3
        assert compute_file_number(2, 0, simple_plan) == SYNTHESIS_OFFSET + 3

    def test_file_in_later_phase(self, simple_plan: Plan) -> None:
        # Batch 1: 2 files, Batch 2: 1 file = 3 files before batch 3
        assert compute_file_number(3, 0, simple_plan) == SYNTHESIS_OFFSET + 4
        assert compute_file_number(3, 1, simple_plan) == SYNTHESIS_OFFSET + 5


class TestBuildManifest:
    def test_correct_count(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        # 3 prefix + 5 files + 1 suffix = 9
        assert len(manifest) == 9

    def test_prefix_entries(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        assert manifest[0].flat_name == "01-overview.md"
        assert manifest[0].kind == "synthesis"
        assert manifest[1].flat_name == "02-architecture.md"
        assert manifest[2].flat_name == "03-concepts.md"

    def test_file_entries_order(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        file_entries = [e for e in manifest if e.kind == "file"]
        assert file_entries[0].original_path == "src/config/loader.py"
        assert file_entries[0].flat_name == "04-src--config--loader.py.md"
        assert file_entries[1].original_path == "src/llm/backend.py"
        assert file_entries[2].original_path == "src/llm/factory.py"
        assert file_entries[3].original_path == "src/core/runner.py"
        assert file_entries[4].original_path == "src/core/architect.py"

    def test_suffix_entry(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        last = manifest[-1]
        assert last.flat_name == "09-getting-started.md"
        assert last.original_path == "GETTING_STARTED"
        assert last.kind == "synthesis"

    def test_layer_assignment(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        file_entries = [e for e in manifest if e.kind == "file"]
        assert file_entries[0].layer == 0  # Phase 0
        assert file_entries[1].layer == 0
        assert file_entries[2].layer == 0
        assert file_entries[3].layer == 1  # Phase 1
        assert file_entries[4].layer == 1

    def test_numbers_are_sequential(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        numbers = [e.number for e in manifest]
        assert numbers == list(range(1, len(manifest) + 1))


class TestInjectNavigation:
    def test_with_both_neighbors(self) -> None:
        prev = FlatFileEntry(1, "01-overview.md", "OVERVIEW", "synthesis")
        next_ = FlatFileEntry(3, "03-concepts.md", "CONCEPTS", "synthesis")
        result = inject_navigation("# Content", prev, next_)
        assert "[<< 01-overview.md]" in result
        assert "[03-concepts.md >>]" in result
        assert "[GUIDE](./GUIDE.md)" in result

    def test_first_entry_no_prev(self) -> None:
        next_ = FlatFileEntry(2, "02-architecture.md", "ARCHITECTURE", "synthesis")
        result = inject_navigation("# Content", None, next_)
        assert "<<" not in result
        assert "[02-architecture.md >>]" in result

    def test_last_entry_no_next(self) -> None:
        prev = FlatFileEntry(8, "08-getting-started.md", "GETTING_STARTED", "synthesis")
        result = inject_navigation("# Content", prev, None)
        assert "[<< 08-getting-started.md]" in result
        assert ">>" not in result


class TestGenerateGuideMd:
    def test_has_all_parts(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        guide = generate_guide_md(manifest, simple_plan)
        assert "## Part I: Big Picture" in guide
        assert "## Part II: Code Walkthrough" in guide
        assert "## Part III: Get Started" in guide

    def test_layers_grouped(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        guide = generate_guide_md(manifest, simple_plan)
        assert "### Layer 0" in guide
        assert "### Layer 1" in guide

    def test_file_links(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        guide = generate_guide_md(manifest, simple_plan)
        assert "04-src--config--loader.py.md" in guide
        assert "`src/config/loader.py`" in guide

    def test_getting_started_in_part_3(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        guide = generate_guide_md(manifest, simple_plan)
        part3_idx = guide.index("## Part III")
        assert "getting-started" in guide[part3_idx:]

    def test_learning_objectives(self, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        guide = generate_guide_md(manifest, simple_plan)
        assert "Understand config and LLM basics" in guide


class TestInjectNavigationAllFiles:
    def test_injects_into_existing_files(self, tmp_path: Path, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        # Write first 3 files
        for entry in manifest[:3]:
            (tmp_path / entry.flat_name).write_text(f"# {entry.original_path}\n")

        inject_navigation_all_files(tmp_path, manifest[:3])

        first = (tmp_path / manifest[0].flat_name).read_text()
        assert "[GUIDE](./GUIDE.md)" in first
        assert ">>" in first
        assert "<<" not in first  # first entry has no prev

    def test_skips_missing_files(self, tmp_path: Path, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        # Only write first file
        (tmp_path / manifest[0].flat_name).write_text("# Test\n")
        # Should not raise
        inject_navigation_all_files(tmp_path, manifest)


class TestCreateBackwardCompatSymlinks:
    def test_top_down_symlinks(self, tmp_path: Path, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        # Write flat files
        for entry in manifest:
            if entry.kind == "synthesis":
                (tmp_path / entry.flat_name).write_text(f"# {entry.original_path}\n")

        create_backward_compat_symlinks(tmp_path, manifest)

        link = tmp_path / "top_down" / "OVERVIEW.md"
        assert link.is_symlink()
        assert link.resolve() == (tmp_path / "01-overview.md").resolve()

    def test_bottom_up_symlinks(self, tmp_path: Path, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        # Write flat files
        for entry in manifest:
            if entry.kind == "file":
                (tmp_path / entry.flat_name).write_text(f"# {entry.original_path}\n")

        create_backward_compat_symlinks(tmp_path, manifest)

        link = tmp_path / "bottom_up" / "src" / "config" / "loader.py.md"
        assert link.is_symlink()

    def test_idempotent(self, tmp_path: Path, simple_plan: Plan) -> None:
        manifest = build_manifest(simple_plan)
        for entry in manifest:
            (tmp_path / entry.flat_name).write_text(f"# {entry.original_path}\n")

        create_backward_compat_symlinks(tmp_path, manifest)
        create_backward_compat_symlinks(tmp_path, manifest)

        link = tmp_path / "top_down" / "OVERVIEW.md"
        assert link.is_symlink()
