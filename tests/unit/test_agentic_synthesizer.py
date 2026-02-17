"""Tests for AgenticSynthesizer and synthesis_tools modules."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lantern_cli.llm.backend import LLMResponse
from lantern_cli.core.synthesis_tools import (
    identify_entry_points,
    prepare_classes_summary,
    prepare_file_details,
    prepare_functions_summary,
    prepare_summaries,
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "batch": 1,
        "file_index": 0,
        "file_path": "src/app/cli.py",
        "analysis": {
            "summary": "CLI entry point for the application.",
            "key_insights": ["Uses argparse for CLI", "Validates params"],
            "functions": ["main(): entry point", "parse_args(): handle CLI"],
            "classes": [],
            "flow": "User calls main -> parse_args -> run",
            "flow_diagram": "graph TD\n    A[User] --> B[main]",
            "references": ["argparse", "sys"],
            "language": "en",
        },
    },
    {
        "batch": 1,
        "file_index": 1,
        "file_path": "src/app/db.py",
        "analysis": {
            "summary": "Database module managing data persistence via SQLite.",
            "key_insights": ["Uses SQLite", "Thread-safe connections"],
            "functions": ["save(): persist data", "load(): read data"],
            "classes": ["Database: wraps SQLite connection"],
            "flow": "save writes to DB, load reads from DB",
            "flow_diagram": "",
            "references": ["sqlite3"],
            "language": "en",
        },
    },
    {
        "batch": 2,
        "file_index": 0,
        "file_path": "src/app/server.py",
        "analysis": {
            "summary": "HTTP server handling REST API requests.",
            "key_insights": ["Flask-based", "RESTful design"],
            "functions": ["start_server(): launch HTTP server", "handle_request(): route handler"],
            "classes": ["APIServer: main server class", "Router: route registry"],
            "flow": "Request arrives -> Router -> handler -> response",
            "flow_diagram": "graph TD\n    Req[Request] --> Router --> Handler --> Resp[Response]",
            "references": ["flask", "src/app/db.py"],
            "language": "en",
        },
    },
]

EMPTY_RECORD = {
    "batch": 3,
    "file_index": 0,
    "file_path": "src/app/__init__.py",
    "analysis": {
        "summary": "unable to analyze",
        "key_insights": [],
        "functions": [],
        "classes": [],
        "flow": "",
        "references": [],
        "language": "en",
    },
}


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
# Tests for synthesis_tools
# ===========================================================================


class TestPrepareSummaries:
    def test_basic_formatting(self) -> None:
        result = prepare_summaries(SAMPLE_RECORDS)
        assert "### src/app/cli.py" in result
        assert "CLI entry point" in result
        assert "Uses argparse for CLI" in result
        assert "### src/app/db.py" in result

    def test_empty_records(self) -> None:
        result = prepare_summaries([])
        assert result == ""

    def test_truncation(self) -> None:
        result = prepare_summaries(SAMPLE_RECORDS, max_chars=50)
        assert "...(truncated)" in result
        assert len(result) <= 50 + len("\n\n...(truncated)")

    def test_skips_records_without_summary(self) -> None:
        records = [{"file_path": "x.py", "analysis": {"summary": ""}}]
        result = prepare_summaries(records)
        assert result.strip() == ""

    def test_handles_non_dict_analysis(self) -> None:
        records = [{"file_path": "x.py", "analysis": "not a dict"}]
        result = prepare_summaries(records)
        assert result.strip() == ""


class TestPrepareFileDetails:
    def test_includes_classes_and_functions(self) -> None:
        result = prepare_file_details(SAMPLE_RECORDS)
        assert "**Classes**: Database" in result
        assert "**Functions**: save()" in result
        assert "**Functions**: main(): entry point" in result

    def test_includes_flow_diagram(self) -> None:
        result = prepare_file_details(SAMPLE_RECORDS)
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_empty_records(self) -> None:
        assert prepare_file_details([]) == ""


class TestPrepareFunctionsSummary:
    def test_groups_by_file(self) -> None:
        result = prepare_functions_summary(SAMPLE_RECORDS)
        assert "### src/app/cli.py" in result
        assert "main(): entry point" in result
        assert "### src/app/db.py" in result
        assert "save(): persist data" in result

    def test_skips_files_without_functions(self) -> None:
        records = [{"file_path": "x.py", "analysis": {"functions": []}}]
        result = prepare_functions_summary(records)
        assert result.strip() == ""


class TestPrepareClassesSummary:
    def test_groups_by_file(self) -> None:
        result = prepare_classes_summary(SAMPLE_RECORDS)
        assert "### src/app/db.py" in result
        assert "Database" in result
        assert "### src/app/server.py" in result
        assert "APIServer" in result

    def test_skips_files_without_classes(self) -> None:
        # cli.py has no classes — it should not appear
        result = prepare_classes_summary(SAMPLE_RECORDS)
        assert "### src/app/cli.py" not in result


class TestIdentifyEntryPoints:
    def test_finds_cli_and_server(self) -> None:
        result = identify_entry_points(SAMPLE_RECORDS)
        assert "src/app/cli.py" in result
        assert "src/app/server.py" in result
        # db.py should not be an entry point
        assert "src/app/db.py" not in result

    def test_detects_main_function(self) -> None:
        records = [
            {
                "file_path": "src/bootstrap.py",
                "analysis": {
                    "summary": "Bootstrap module.",
                    "functions": ["main(): start app"],
                    "classes": [],
                },
            }
        ]
        result = identify_entry_points(records)
        assert "src/bootstrap.py" in result

    def test_no_entry_points(self) -> None:
        records = [
            {
                "file_path": "src/utils.py",
                "analysis": {
                    "summary": "Utility helpers.",
                    "functions": ["helper(): do something"],
                    "classes": [],
                },
            }
        ]
        result = identify_entry_points(records)
        assert "No clear entry points" in result


# ===========================================================================
# Tests for AgenticSynthesizer
# ===========================================================================


class TestAgenticSynthesizer:
    """Tests for the LangGraph-based agentic synthesizer."""

    @pytest.fixture
    def sense_dir(self, tmp_path: Path) -> Path:
        """Create a tmp project with .sense files."""
        sense = tmp_path / ".lantern" / "sense"
        sense.mkdir(parents=True)
        (sense / "batch_0001.sense").write_text(
            json.dumps(SAMPLE_RECORDS, ensure_ascii=False, indent=2)
        )
        return sense

    @pytest.fixture
    def plan_file(self, tmp_path: Path) -> Path:
        """Create a lantern_plan.md with a Mermaid block."""
        lantern_dir = tmp_path / ".lantern"
        lantern_dir.mkdir(parents=True, exist_ok=True)
        plan_content = (
            "# Plan\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    cli_py --> db_py\n"
            "    server_py --> db_py\n"
            "```\n"
        )
        plan_path = lantern_dir / "lantern_plan.md"
        plan_path.write_text(plan_content)
        return plan_path

    def test_generate_top_down_docs_produces_all_files(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """The agentic synthesizer should produce all 4 top-down docs."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("LLM generated architecture analysis content.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        out_dir = synth.output_dir
        assert (out_dir / "OVERVIEW.md").exists()
        assert (out_dir / "ARCHITECTURE.md").exists()
        assert (out_dir / "GETTING_STARTED.md").exists()
        assert (out_dir / "CONCEPTS.md").exists()

    def test_documents_contain_llm_output(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """Each document should contain the LLM-generated content."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Unique LLM content marker XYZ123.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        out_dir = synth.output_dir
        for fname in ["OVERVIEW.md", "ARCHITECTURE.md", "GETTING_STARTED.md", "CONCEPTS.md"]:
            content = (out_dir / fname).read_text(encoding="utf-8")
            assert "Unique LLM content marker XYZ123." in content

    def test_documents_have_agentic_header(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """Documents should be marked as generated by Agentic Synthesis."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Content.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        out_dir = synth.output_dir
        overview = (out_dir / "OVERVIEW.md").read_text(encoding="utf-8")
        assert "Agentic Synthesis" in overview

    def test_architecture_includes_dependency_graph(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """ARCHITECTURE.md should embed the dependency Mermaid from plan."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Architecture body.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        arch = (synth.output_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "```mermaid" in arch
        assert "cli_py --> db_py" in arch

    def test_llm_called_six_times(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """The graph has 6 nodes, each invoking the LLM once."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Content.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        assert llm.invoke.call_count == 6

    def test_empty_sense_dir(self, tmp_path: Path) -> None:
        """No crash when sense directory is empty."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Should not be called.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        # No output files should be created
        assert not synth.output_dir.exists()
        assert llm.invoke.call_count == 0

    def test_all_empty_records_filtered(self, tmp_path: Path) -> None:
        """No crash when all records are empty/unanalyzable."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        (sense_dir / "batch_0001.sense").write_text(json.dumps([EMPTY_RECORD]))

        llm = _make_backend_mock("Should not be called.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        assert llm.invoke.call_count == 0

    def test_sequential_node_context_building(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """Later nodes should receive output from earlier nodes as context."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        # Return distinct content for each of the 6 LLM calls
        llm = _make_backend_mock_sequential([
            "PATTERNS: Factory pattern found in server.py",  # identify_patterns
            "COMPARISON: cli.py and server.py are entry points",  # cross_compare
            "Overview document body",  # generate_overview
            "Architecture document body",  # generate_architecture
            "Getting started document body",  # generate_getting_started
            "Concepts document body",  # generate_concepts
        ])
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        # Verify all 6 calls were made
        assert llm.invoke.call_count == 6

        # Check that later calls received earlier outputs in their prompt.
        # The cross_compare call (2nd) should include patterns_analysis in its prompt.
        second_call_prompt = llm.invoke.call_args_list[1][0][0]
        assert "Factory pattern" in second_call_prompt

    def test_language_parameter_passed_to_prompts(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """The language parameter should appear in LLM system messages."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("Content.")
        synth = AgenticSynthesizer(tmp_path, llm, language="zh-TW")
        synth.generate_top_down_docs()

        # Check first call's prompt includes zh-TW
        first_call_prompt = llm.invoke.call_args_list[0][0][0]
        assert "zh-TW" in first_call_prompt

    def test_output_dir_configurable(self, tmp_path: Path) -> None:
        """Custom output_dir should be respected."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        sense_dir = tmp_path / "custom_out" / "sense"
        sense_dir.mkdir(parents=True)
        (sense_dir / "batch_0001.sense").write_text(
            json.dumps(SAMPLE_RECORDS, ensure_ascii=False)
        )

        llm = _make_backend_mock("Content.")
        synth = AgenticSynthesizer(tmp_path, llm, language="en", output_dir="custom_out")
        synth.generate_top_down_docs()

        assert (tmp_path / "custom_out" / "output" / "en" / "top_down" / "OVERVIEW.md").exists()

    def test_is_empty_record(self) -> None:
        """Test the empty record detection."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        assert AgenticSynthesizer._is_empty_record(EMPTY_RECORD)
        assert not AgenticSynthesizer._is_empty_record(SAMPLE_RECORDS[0])
        assert AgenticSynthesizer._is_empty_record({"analysis": {"summary": ""}})
        assert AgenticSynthesizer._is_empty_record({"analysis": "not a dict"})

    def test_load_mermaid_from_plan(self, tmp_path: Path, plan_file: Path) -> None:
        """Test Mermaid extraction from plan file."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("x")
        synth = AgenticSynthesizer(tmp_path, llm)
        mermaid = synth._load_mermaid_from_plan()
        assert "cli_py --> db_py" in mermaid
        assert "server_py --> db_py" in mermaid

    def test_load_mermaid_no_plan(self, tmp_path: Path) -> None:
        """Missing plan file returns empty string."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        llm = _make_backend_mock("x")
        synth = AgenticSynthesizer(tmp_path, llm)
        assert synth._load_mermaid_from_plan() == ""

    def test_doc_truncation(
        self, tmp_path: Path, sense_dir: Path, plan_file: Path
    ) -> None:
        """Very long LLM output should be truncated."""
        from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

        long_content = "A" * 20000
        llm = _make_backend_mock(long_content)
        synth = AgenticSynthesizer(tmp_path, llm, language="en")
        synth.generate_top_down_docs()

        overview = (synth.output_dir / "OVERVIEW.md").read_text(encoding="utf-8")
        assert "...(truncated)..." in overview


class TestBuildSynthesisGraph:
    """Tests for the graph builder function."""

    def test_graph_compiles(self) -> None:
        """The graph should compile without errors."""
        from lantern_cli.core.agentic_synthesizer import build_synthesis_graph

        llm = _make_backend_mock("x")
        compiled = build_synthesis_graph(llm)
        assert compiled is not None

    def test_graph_has_expected_nodes(self) -> None:
        """The compiled graph should contain all 6 synthesis nodes."""
        from lantern_cli.core.agentic_synthesizer import build_synthesis_graph

        llm = _make_backend_mock("x")
        compiled = build_synthesis_graph(llm)

        # LangGraph compiled graphs expose their structure via get_graph()
        graph_repr = compiled.get_graph()
        node_ids = {node.id for node in graph_repr.nodes.values()}
        expected_nodes = {
            "identify_patterns",
            "cross_compare",
            "generate_overview",
            "generate_architecture",
            "generate_getting_started",
            "generate_concepts",
        }
        assert expected_nodes.issubset(node_ids)
