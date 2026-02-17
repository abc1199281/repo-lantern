"""Tests for AgenticPlanner and planning_tools modules."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lantern_cli.llm.backend import LLMResponse
from lantern_cli.core.architect import Batch, Phase, Plan
from lantern_cli.core.planning_tools import (
    prepare_dependency_summary,
    prepare_file_tree,
    prepare_layer_summary,
    sample_key_files,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_FILE_LIST = [
    "src/core/main.py",
    "src/core/config.py",
    "src/core/utils.py",
    "src/api/routes.py",
    "src/api/handlers.py",
    "src/models/user.py",
    "src/models/base.py",
    "tests/test_main.py",
]

SAMPLE_DEPENDENCIES: dict[str, set[str]] = {
    "src/core/main.py": {"src/core/config.py", "src/api/routes.py"},
    "src/core/config.py": set(),
    "src/core/utils.py": set(),
    "src/api/routes.py": {"src/api/handlers.py", "src/models/user.py"},
    "src/api/handlers.py": {"src/models/user.py", "src/core/utils.py"},
    "src/models/user.py": {"src/models/base.py"},
    "src/models/base.py": set(),
    "tests/test_main.py": {"src/core/main.py"},
}

SAMPLE_REVERSE_DEPENDENCIES: dict[str, set[str]] = {
    "src/core/config.py": {"src/core/main.py"},
    "src/api/routes.py": {"src/core/main.py"},
    "src/api/handlers.py": {"src/api/routes.py"},
    "src/models/user.py": {"src/api/routes.py", "src/api/handlers.py"},
    "src/models/base.py": {"src/models/user.py"},
    "src/core/utils.py": {"src/api/handlers.py"},
    "src/core/main.py": {"tests/test_main.py"},
}

SAMPLE_LAYERS: dict[str, int] = {
    "src/core/config.py": 0,
    "src/core/utils.py": 0,
    "src/models/base.py": 0,
    "src/models/user.py": 1,
    "src/api/handlers.py": 2,
    "src/api/routes.py": 3,
    "src/core/main.py": 4,
    "tests/test_main.py": 5,
}

# Valid semantic groups JSON that an LLM might return
VALID_GROUPS_JSON = json.dumps([
    ["src/models/base.py", "src/models/user.py"],
    ["src/core/config.py", "src/core/utils.py"],
    ["src/api/routes.py", "src/api/handlers.py"],
    ["src/core/main.py"],
    ["tests/test_main.py"],
])

# Valid hints JSON that an LLM might return
VALID_HINTS_JSON = json.dumps({
    "0": "Analyze the data model hierarchy. Focus on base class patterns.",
    "1": "These are utility modules. Identify shared helpers and configuration.",
    "2": "API layer files. Compare route definitions and handler patterns.",
    "3": "Main entry point. Trace the startup flow and dependency injection.",
    "4": "Test file. Verify test coverage patterns.",
})


def _make_backend_mock(content: str = "Generated LLM content") -> MagicMock:
    """Create a Backend mock that returns the same content for every invoke call."""
    backend = MagicMock()
    backend.invoke.return_value = LLMResponse(content=content)
    backend.model_name = "test-model"
    return backend


def _make_backend_mock_sequential(contents: list[str]) -> MagicMock:
    """Create a Backend mock that returns different content on successive calls."""
    backend = MagicMock()
    responses = [LLMResponse(content=c) for c in contents]
    backend.invoke.side_effect = responses
    backend.model_name = "test-model"
    return backend


# ===========================================================================
# Tests for planning_tools
# ===========================================================================


class TestPrepareFileTree:
    def test_basic_tree(self) -> None:
        result = prepare_file_tree(SAMPLE_FILE_LIST)
        assert "src" in result
        assert "core" in result
        assert "main.py" in result
        assert "api" in result
        assert "routes.py" in result

    def test_empty_list(self) -> None:
        result = prepare_file_tree([])
        assert "No files found" in result

    def test_single_file(self) -> None:
        result = prepare_file_tree(["main.py"])
        assert "main.py" in result

    def test_truncation(self) -> None:
        result = prepare_file_tree(SAMPLE_FILE_LIST, max_chars=30)
        assert "...(truncated)" in result

    def test_nested_structure(self) -> None:
        result = prepare_file_tree(["a/b/c/d.py", "a/b/e.py"])
        assert "a" in result
        assert "b" in result
        assert "c" in result
        assert "d.py" in result
        assert "e.py" in result


class TestPrepareDependencySummary:
    def test_basic_format(self) -> None:
        result = prepare_dependency_summary(SAMPLE_DEPENDENCIES)
        assert "src/core/main.py" in result
        assert "src/core/config.py" in result

    def test_empty_dependencies(self) -> None:
        result = prepare_dependency_summary({})
        assert "No dependencies detected" in result

    def test_isolated_files_noted(self) -> None:
        result = prepare_dependency_summary(SAMPLE_DEPENDENCIES)
        assert "Isolated files" in result
        assert "src/core/config.py" in result  # has no outgoing deps

    def test_truncation(self) -> None:
        result = prepare_dependency_summary(SAMPLE_DEPENDENCIES, max_chars=50)
        assert "...(truncated)" in result

    def test_sorted_by_dependency_count(self) -> None:
        result = prepare_dependency_summary(SAMPLE_DEPENDENCIES)
        lines = [l for l in result.split("\n") if l.startswith("- ")]
        # First line should be the file with most dependencies
        if lines:
            assert "src/core/main.py" in lines[0] or "src/api/routes.py" in lines[0]


class TestPrepareLayerSummary:
    def test_basic_format(self) -> None:
        result = prepare_layer_summary(SAMPLE_LAYERS)
        assert "Layer 0" in result
        assert "leaf nodes" in result
        assert "Layer 1" in result
        assert "src/models/user.py" in result

    def test_empty_layers(self) -> None:
        result = prepare_layer_summary({})
        assert "No layer information" in result

    def test_cycle_layer(self) -> None:
        layers = {"a.py": -1, "b.py": -1}
        result = prepare_layer_summary(layers)
        assert "Cycle" in result
        assert "circular dependencies" in result

    def test_truncation(self) -> None:
        result = prepare_layer_summary(SAMPLE_LAYERS, max_chars=50)
        assert "...(truncated)" in result

    def test_file_counts(self) -> None:
        result = prepare_layer_summary(SAMPLE_LAYERS)
        # Layer 0 has 3 files
        assert "3 file(s)" in result


class TestSampleKeyFiles:
    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        """Create a minimal project with sample files."""
        for fp in SAMPLE_FILE_LIST:
            file_path = tmp_path / fp
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f"# {fp}\ndef example():\n    pass\n")
        return tmp_path

    def test_samples_files(self, project_dir: Path) -> None:
        result = sample_key_files(
            SAMPLE_FILE_LIST,
            SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES,
            project_dir,
        )
        # Should include key files
        assert "main.py" in result
        assert "```" in result

    def test_prioritizes_entry_points(self, project_dir: Path) -> None:
        result = sample_key_files(
            SAMPLE_FILE_LIST,
            SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES,
            project_dir,
            max_files=2,
        )
        # main.py should be sampled (entry point keyword + dependents)
        assert "main.py" in result

    def test_respects_max_files(self, project_dir: Path) -> None:
        result = sample_key_files(
            SAMPLE_FILE_LIST,
            SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES,
            project_dir,
            max_files=2,
        )
        # Should have at most 2 file headers
        count = result.count("### ")
        assert count <= 2

    def test_empty_file_list(self, project_dir: Path) -> None:
        result = sample_key_files(
            [], {}, {}, project_dir
        )
        assert "No files available" in result

    def test_handles_missing_files(self, project_dir: Path) -> None:
        result = sample_key_files(
            ["nonexistent.py"],
            {},
            {},
            project_dir,
        )
        assert "unable to read" in result

    def test_truncates_long_files(self, project_dir: Path) -> None:
        # Create a file with many lines
        long_file = project_dir / "src" / "core" / "main.py"
        long_file.write_text("\n".join(f"line {i}" for i in range(200)))
        result = sample_key_files(
            ["src/core/main.py"],
            {},
            {},
            project_dir,
            max_lines_per_file=10,
        )
        assert "more lines" in result


# ===========================================================================
# Tests for AgenticPlanner
# ===========================================================================


class TestAgenticPlanner:
    """Tests for the LangGraph-based agentic planner."""

    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        """Create a minimal project with sample files."""
        for fp in SAMPLE_FILE_LIST:
            file_path = tmp_path / fp
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f"# {fp}\ndef example():\n    pass\n")
        return tmp_path

    def test_generate_enhanced_plan_returns_plan(self, project_dir: Path) -> None:
        """The planner should return a Plan object."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure: CLI tool with API layer",  # analyze_structure
            "Patterns: MVC architecture",  # identify_patterns
            VALID_GROUPS_JSON,  # semantic_grouping
            VALID_HINTS_JSON,  # generate_hints
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        assert isinstance(plan, Plan)
        assert len(plan.phases) > 0

    def test_all_files_covered(self, project_dir: Path) -> None:
        """Every file should appear in exactly one batch."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure analysis",
            "Pattern analysis",
            VALID_GROUPS_JSON,
            VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        all_files = set()
        for phase in plan.phases:
            for batch in phase.batches:
                for f in batch.files:
                    assert f not in all_files, f"File {f} appears in multiple batches"
                    all_files.add(f)

        assert all_files == set(SAMPLE_FILE_LIST)

    def test_batch_hints_applied(self, project_dir: Path) -> None:
        """Batches should have hints from the LLM."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure analysis",
            "Pattern analysis",
            VALID_GROUPS_JSON,
            VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        # At least some batches should have hints
        hints = [b.hint for p in plan.phases for b in p.batches if b.hint]
        assert len(hints) > 0
        assert any("model" in h.lower() or "hierarchy" in h.lower() for h in hints)

    def test_llm_called_four_times(self, project_dir: Path) -> None:
        """The graph has 4 nodes, each invoking the LLM once."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure analysis",
            "Pattern analysis",
            VALID_GROUPS_JSON,
            VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        assert backend.invoke.call_count == 4

    def test_sequential_context_building(self, project_dir: Path) -> None:
        """Later nodes should receive output from earlier nodes."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "STRUCTURE: This is a layered CLI application",
            "PATTERNS: Factory pattern in handlers, MVC overall",
            VALID_GROUPS_JSON,
            VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        # identify_patterns (2nd call) should include structure_analysis
        second_prompt = backend.invoke.call_args_list[1][0][0]
        assert "layered CLI application" in second_prompt

        # semantic_grouping (3rd call) should include patterns_analysis
        third_prompt = backend.invoke.call_args_list[2][0][0]
        assert "Factory pattern" in third_prompt

    def test_language_parameter_passed(self, project_dir: Path) -> None:
        """Language should appear in LLM prompts."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure", "Patterns", VALID_GROUPS_JSON, VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="zh-TW")
        planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        first_prompt = backend.invoke.call_args_list[0][0][0]
        assert "zh-TW" in first_prompt

    def test_empty_file_list(self, project_dir: Path) -> None:
        """Empty file list should return empty plan without LLM calls."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock("Should not be called")
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan([], {}, {}, {})

        assert len(plan.phases) == 0
        assert backend.invoke.call_count == 0

    def test_batch_size_respected(self, project_dir: Path) -> None:
        """No batch should exceed batch_size."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure", "Patterns", VALID_GROUPS_JSON, VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
            batch_size=3,
        )

        for phase in plan.phases:
            for batch in phase.batches:
                assert len(batch.files) <= 3

    def test_plan_to_markdown_includes_hints(self, project_dir: Path) -> None:
        """Plan.to_markdown() should include batch hints."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure", "Patterns", VALID_GROUPS_JSON, VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        md = plan.to_markdown()
        assert "Hint:" in md

    def test_fallback_on_invalid_groups_json(self, project_dir: Path) -> None:
        """Invalid JSON from LLM should fall back to layer-based grouping."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure",
            "Patterns",
            "This is not valid JSON at all!",  # Invalid groups
            "{}",  # Empty hints
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        # Should still produce a valid plan with all files
        all_files = {f for p in plan.phases for b in p.batches for f in b.files}
        assert all_files == set(SAMPLE_FILE_LIST)

    def test_fallback_on_invalid_hints_json(self, project_dir: Path) -> None:
        """Invalid hints JSON should not crash, just produce batches without hints."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure",
            "Patterns",
            VALID_GROUPS_JSON,
            "Not valid JSON for hints!",  # Invalid hints
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        # Plan should still be valid, just without hints
        assert len(plan.phases) > 0
        all_files = {f for p in plan.phases for b in p.batches for f in b.files}
        assert all_files == set(SAMPLE_FILE_LIST)

    def test_missing_files_in_groups_are_added(self, project_dir: Path) -> None:
        """Files not mentioned in semantic groups should still be included."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        # Groups that only cover some files
        partial_groups = json.dumps([
            ["src/models/base.py", "src/models/user.py"],
            ["src/core/main.py"],
        ])

        backend = _make_backend_mock_sequential([
            "Structure",
            "Patterns",
            partial_groups,
            VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        all_files = {f for p in plan.phases for b in p.batches for f in b.files}
        assert all_files == set(SAMPLE_FILE_LIST)

    def test_confidence_reflects_parsing_success(self, project_dir: Path) -> None:
        """Confidence should be high when parsing succeeds."""
        from lantern_cli.core.agentic_planner import AgenticPlanner

        backend = _make_backend_mock_sequential([
            "Structure", "Patterns", VALID_GROUPS_JSON, VALID_HINTS_JSON,
        ])
        planner = AgenticPlanner(project_dir, backend, language="en")
        plan = planner.generate_enhanced_plan(
            SAMPLE_FILE_LIST, SAMPLE_DEPENDENCIES,
            SAMPLE_REVERSE_DEPENDENCIES, SAMPLE_LAYERS,
        )

        assert plan.confidence_score >= 0.8


class TestBuildPlanningGraph:
    """Tests for the graph builder function."""

    def test_graph_compiles(self) -> None:
        """The graph should compile without errors."""
        from lantern_cli.core.agentic_planner import build_planning_graph

        backend = _make_backend_mock("x")
        compiled = build_planning_graph(backend)
        assert compiled is not None

    def test_graph_has_expected_nodes(self) -> None:
        """The compiled graph should contain all 4 planning nodes."""
        from lantern_cli.core.agentic_planner import build_planning_graph

        backend = _make_backend_mock("x")
        compiled = build_planning_graph(backend)

        graph_repr = compiled.get_graph()
        node_ids = {node.id for node in graph_repr.nodes.values()}
        expected_nodes = {
            "analyze_structure",
            "identify_patterns",
            "semantic_grouping",
            "generate_hints",
        }
        assert expected_nodes.issubset(node_ids)


class TestJsonExtraction:
    """Tests for JSON extraction helpers."""

    def test_extract_json_array_plain(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_array

        result = _extract_json_array('[["a.py", "b.py"], ["c.py"]]')
        assert result == [["a.py", "b.py"], ["c.py"]]

    def test_extract_json_array_with_code_block(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_array

        text = 'Here are the groups:\n```json\n[["a.py"], ["b.py"]]\n```'
        result = _extract_json_array(text)
        assert result == [["a.py"], ["b.py"]]

    def test_extract_json_array_with_preamble(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_array

        text = 'Based on my analysis:\n[["a.py", "b.py"]]'
        result = _extract_json_array(text)
        assert result == [["a.py", "b.py"]]

    def test_extract_json_array_invalid_raises(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_array

        with pytest.raises(ValueError, match="Could not extract"):
            _extract_json_array("This has no JSON at all")

    def test_extract_json_object_plain(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_object

        result = _extract_json_object('{"0": "hint for batch 0"}')
        assert result == {"0": "hint for batch 0"}

    def test_extract_json_object_with_code_block(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_object

        text = '```json\n{"0": "hint"}\n```'
        result = _extract_json_object(text)
        assert result == {"0": "hint"}

    def test_extract_json_object_invalid_raises(self) -> None:
        from lantern_cli.core.agentic_planner import _extract_json_object

        with pytest.raises(ValueError, match="Could not extract"):
            _extract_json_object("No JSON here")


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_enforce_batch_size(self) -> None:
        from lantern_cli.core.agentic_planner import _enforce_batch_size

        groups = [["a.py", "b.py", "c.py", "d.py", "e.py"], ["f.py"]]
        result = _enforce_batch_size(groups, batch_size=3)
        assert all(len(g) <= 3 for g in result)
        # All files should still be present
        all_files = [f for g in result for f in g]
        assert set(all_files) == {"a.py", "b.py", "c.py", "d.py", "e.py", "f.py"}

    def test_enforce_batch_size_no_split_needed(self) -> None:
        from lantern_cli.core.agentic_planner import _enforce_batch_size

        groups = [["a.py", "b.py"], ["c.py"]]
        result = _enforce_batch_size(groups, batch_size=3)
        assert result == groups

    def test_fallback_layer_groups(self) -> None:
        from lantern_cli.core.agentic_planner import _fallback_layer_groups

        result = _fallback_layer_groups(SAMPLE_FILE_LIST, SAMPLE_LAYERS, batch_size=3)
        # All files should be present
        all_files = [f for g in result for f in g]
        assert set(all_files) == set(SAMPLE_FILE_LIST)
        # Each group should have at most 3 files
        assert all(len(g) <= 3 for g in result)

    def test_fallback_layer_groups_respects_layers(self) -> None:
        from lantern_cli.core.agentic_planner import _fallback_layer_groups

        result = _fallback_layer_groups(SAMPLE_FILE_LIST, SAMPLE_LAYERS, batch_size=3)
        # First group should be layer 0 files
        layer0_files = {"src/core/config.py", "src/core/utils.py", "src/models/base.py"}
        first_group_files = set(result[0])
        assert first_group_files.issubset(layer0_files)


class TestBatchHintField:
    """Tests for the Batch.hint field added in Phase 2."""

    def test_batch_default_hint_is_empty(self) -> None:
        batch = Batch(id=1, files=["a.py"])
        assert batch.hint == ""

    def test_batch_with_hint(self) -> None:
        batch = Batch(id=1, files=["a.py"], hint="Focus on the Factory pattern.")
        assert batch.hint == "Focus on the Factory pattern."

    def test_plan_to_markdown_with_hints(self) -> None:
        batch = Batch(id=1, files=["a.py", "b.py"], hint="Compare implementations.")
        phase = Phase(id=1, batches=[batch], learning_objectives=["Understand patterns"])
        plan = Plan(phases=[phase])
        md = plan.to_markdown()
        assert "Hint: Compare implementations." in md

    def test_plan_to_markdown_without_hints(self) -> None:
        batch = Batch(id=1, files=["a.py"])
        phase = Phase(id=1, batches=[batch])
        plan = Plan(phases=[phase])
        md = plan.to_markdown()
        assert "Hint:" not in md
