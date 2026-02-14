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
            "risks": [],
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
            "risks": ["No migration support"],
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

        # Architecture should contain classes, references, and file subheadings
        assert "### `src/app/db.py`" in arch
        assert "Database" in arch
        assert "sqlite3" in arch

        # Getting Started should contain functions grouped by file
        assert "### `src/app/cli.py`" in started
        assert "main(): entry point" in started
        assert "save(): persist data" in started

        # Concepts should contain classes, insights, risks grouped by file
        assert "### `src/app/db.py`" in concepts
        assert "Database" in concepts
        assert "No migration support" in concepts

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
