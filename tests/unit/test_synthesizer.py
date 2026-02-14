"""Tests for Synthesizer module."""
import json
from pathlib import Path

import pytest

from lantern_cli.core.synthesizer import Synthesizer


SAMPLE_SENSE_RECORDS = [
    {
        "batch": 1,
        "file_index": 0,
        "file_path": "src/app/cli.py",
        "analysis": {
            "summary": "Module A handles user input.",
            "key_insights": ["Uses argparse for CLI", "Validates params"],
            "functions": ["main(): entry point", "parse_args(): handle CLI"],
            "classes": [],
            "flow": "User calls main -> parse_args -> run",
            "references": ["argparse", "sys"],
            "language": "en",
        },
    },
    {
        "batch": 1,
        "file_index": 1,
        "file_path": "src/app/db.py",
        "analysis": {
            "summary": "Module B manages data persistence.",
            "key_insights": ["Uses SQLite", "Thread-safe"],
            "functions": ["save(): persist data", "load(): read data"],
            "classes": ["Database: wraps SQLite connection"],
            "flow": "save writes to DB, load reads from DB",
            "references": ["sqlite3"],
            "language": "en",
        },
    },
]

EMPTY_RECORD = {
    "batch": 1,
    "file_index": 2,
    "file_path": "src/app/__init__.py",
    "analysis": {
        "summary": "文件內容未提供，無法進行分析。",
        "key_insights": [],
        "functions": [],
        "classes": [],
        "flow": "",
        "risks": [],
        "references": [],
        "language": "zh-TW",
    },
}


class TestSynthesizer:
    """Test Synthesizer class."""

    @pytest.fixture
    def synthesizer(self, tmp_path: Path) -> Synthesizer:
        """Create a Synthesizer instance with JSON .sense files."""
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        (sense_dir / "batch_0001.sense").write_text(
            json.dumps(SAMPLE_SENSE_RECORDS, ensure_ascii=False, indent=2)
        )
        return Synthesizer(root_path=tmp_path)

    def test_load_sense_files(self, synthesizer: Synthesizer) -> None:
        """Test loading and parsing .sense JSON files."""
        records = synthesizer.load_sense_files()
        assert len(records) == 2
        assert records[0]["analysis"]["summary"] == "Module A handles user input."
        assert records[1]["analysis"]["summary"] == "Module B manages data persistence."

    def test_generate_top_down_docs(self, synthesizer: Synthesizer) -> None:
        """Test generating top-down documentation with file-grouped sections."""
        synthesizer.generate_top_down_docs()

        out_dir = synthesizer.output_dir
        overview = (out_dir / "OVERVIEW.md").read_text(encoding="utf-8")
        arch = (out_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
        started = (out_dir / "GETTING_STARTED.md").read_text(encoding="utf-8")
        concepts = (out_dir / "CONCEPTS.md").read_text(encoding="utf-8")

        # Overview should contain summaries grouped by file
        assert "### `src/app/cli.py`" in overview
        assert "### `src/app/db.py`" in overview
        assert "Module A handles user input." in overview
        assert "Uses argparse for CLI" in overview

        # Architecture should contain classes and file subheadings
        # (references are no longer dumped here — replaced by flow_diagram)
        assert "### `src/app/db.py`" in arch
        assert "Database" in arch

        # Getting Started should contain functions grouped by file
        assert "### `src/app/cli.py`" in started
        assert "main(): entry point" in started
        assert "save(): persist data" in started

        # Concepts should contain classes (key_insights deduplicated to OVERVIEW)
        assert "### `src/app/db.py`" in concepts
        assert "Database" in concepts

    def test_empty_sense_files(self, tmp_path: Path) -> None:
        """Test behavior with no sense files."""
        synth = Synthesizer(root_path=tmp_path)
        records = synth.load_sense_files()
        assert len(records) == 0

    def test_malformed_sense_file(self, tmp_path: Path) -> None:
        """Test that malformed JSON .sense files are skipped gracefully."""
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        (sense_dir / "batch_0001.sense").write_text("not valid json")
        (sense_dir / "batch_0002.sense").write_text(
            json.dumps([{
                "file_path": "ok.py",
                "analysis": {"summary": "OK", "key_insights": []},
            }])
        )

        synth = Synthesizer(root_path=tmp_path)
        records = synth.load_sense_files()
        assert len(records) == 1
        assert records[0]["analysis"]["summary"] == "OK"

    def test_empty_file_filtered(self, tmp_path: Path) -> None:
        """Test that records for empty/unanalyzable files are filtered out."""
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        all_records = SAMPLE_SENSE_RECORDS + [EMPTY_RECORD]
        (sense_dir / "batch_0001.sense").write_text(
            json.dumps(all_records, ensure_ascii=False, indent=2)
        )

        synth = Synthesizer(root_path=tmp_path)
        synth.generate_top_down_docs()

        overview = (synth.output_dir / "OVERVIEW.md").read_text(encoding="utf-8")
        # The empty record's summary should NOT appear
        assert "未提供" not in overview
        assert "無法進行分析" not in overview
        # Real records should still be there
        assert "Module A handles user input." in overview

    def test_file_path_subheadings(self, synthesizer: Synthesizer) -> None:
        """Test that output contains file path subheadings."""
        synthesizer.generate_top_down_docs()

        arch = (synthesizer.output_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
        # Each file should have its own ### subheading
        assert "### `src/app/cli.py`" in arch
        assert "### `src/app/db.py`" in arch

    def test_load_mermaid_from_plan(self, tmp_path: Path) -> None:
        """Test extracting Mermaid block from lantern_plan.md."""
        plan_dir = tmp_path / ".lantern"
        plan_dir.mkdir(parents=True)
        plan_content = (
            "# Lantern Plan\n\n"
            "## Dependency Graph\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    A --> B\n"
            "```\n\n"
            "## Phase 1\n"
        )
        (plan_dir / "lantern_plan.md").write_text(plan_content)

        synth = Synthesizer(root_path=tmp_path)
        mermaid = synth._load_mermaid_from_plan()
        assert "```mermaid" in mermaid
        assert "A --> B" in mermaid
        assert mermaid.endswith("```")

    def test_load_mermaid_from_plan_no_file(self, tmp_path: Path) -> None:
        """Test that missing plan file returns empty string."""
        synth = Synthesizer(root_path=tmp_path)
        assert synth._load_mermaid_from_plan() == ""

    def test_load_mermaid_from_plan_no_mermaid_block(self, tmp_path: Path) -> None:
        """Test that plan without mermaid block returns empty string."""
        plan_dir = tmp_path / ".lantern"
        plan_dir.mkdir(parents=True)
        (plan_dir / "lantern_plan.md").write_text("# Plan\n\nNo diagrams here.\n")

        synth = Synthesizer(root_path=tmp_path)
        assert synth._load_mermaid_from_plan() == ""

    def test_references_to_mermaid_with_file_refs(self) -> None:
        """Test Mermaid generation from file-like references."""
        result = Synthesizer._references_to_mermaid(
            "src/app/cli.py",
            ["argparse", "src/app/db.py", "config.json (JSON Schema)"],
        )
        # argparse has no dot-with-extension or slash so should be skipped
        # src/app/db.py has slash so should appear
        # config.json has a dot and no space so should appear
        assert "```mermaid" in result
        assert "src_app_db_py" in result
        assert "config_json" in result

    def test_references_to_mermaid_no_usable_refs(self) -> None:
        """Test that prose-only references produce no Mermaid."""
        result = Synthesizer._references_to_mermaid(
            "src/app/cli.py",
            ["argparse", "some library"],
        )
        assert result == ""

    def test_references_to_mermaid_empty(self) -> None:
        """Test that empty references produce no Mermaid."""
        result = Synthesizer._references_to_mermaid("src/app/cli.py", [])
        assert result == ""

    def test_architecture_embeds_mermaid_from_plan(self, tmp_path: Path) -> None:
        """Test that ARCHITECTURE.md includes the dependency graph from plan."""
        lantern_dir = tmp_path / ".lantern"
        sense_dir = lantern_dir / "sense"
        sense_dir.mkdir(parents=True)

        # Write a plan with Mermaid
        plan_content = (
            "# Plan\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    cli_py --> db_py\n"
            "```\n"
        )
        (lantern_dir / "lantern_plan.md").write_text(plan_content)

        # Write sense records
        (sense_dir / "batch_0001.sense").write_text(
            json.dumps(SAMPLE_SENSE_RECORDS, ensure_ascii=False, indent=2)
        )

        synth = Synthesizer(root_path=tmp_path)
        synth.generate_top_down_docs()

        arch = (synth.output_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "## Dependency Graph" in arch
        assert "```mermaid" in arch
        assert "cli_py --> db_py" in arch
        # Component Details section should also be present
        assert "## Component Details" in arch

    def test_flow_diagram_in_architecture(self, tmp_path: Path) -> None:
        """Test that flow_diagram Mermaid is embedded in ARCHITECTURE."""
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        records = [
            {
                "batch": 1,
                "file_index": 0,
                "file_path": "src/app/cli.py",
                "analysis": {
                    "summary": "CLI entry point.",
                    "key_insights": ["Simple CLI"],
                    "functions": ["main()"],
                    "classes": [],
                    "flow": "User calls main",
                    "flow_diagram": "graph TD\n    A[User] --> B[main]\n    B --> C[run]",
                            "references": [],
                    "language": "en",
                },
            },
        ]
        (sense_dir / "batch_0001.sense").write_text(
            json.dumps(records, ensure_ascii=False, indent=2)
        )
        synth = Synthesizer(root_path=tmp_path)
        synth.generate_top_down_docs()

        arch = (synth.output_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
        assert "```mermaid" in arch
        assert "graph TD" in arch
        assert "A[User] --> B[main]" in arch

        started = (synth.output_dir / "GETTING_STARTED.md").read_text(encoding="utf-8")
        assert "```mermaid" in started
        assert "graph TD" in started
