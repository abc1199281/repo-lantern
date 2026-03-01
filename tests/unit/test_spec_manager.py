"""Tests for the spec_manager module."""

from pathlib import Path

from lantern_cli.core.spec_manager import (
    SpecEntry,
    _parse_modules_response,
    _table_to_markdown,
    extract_markdown,
    get_all_spec_summaries,
    get_spec_context,
    load_specs,
    save_specs,
)


class TestTableToMarkdown:
    def test_basic_table(self) -> None:
        table = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        result = _table_to_markdown(table)
        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result
        assert "| Bob | 25 |" in result

    def test_empty_table(self) -> None:
        assert _table_to_markdown([]) == ""

    def test_none_cells(self) -> None:
        table = [["A", "B"], [None, "val"]]
        result = _table_to_markdown(table)
        assert "|  | val |" in result

    def test_short_row_padded(self) -> None:
        table = [["A", "B", "C"], ["only_one"]]
        result = _table_to_markdown(table)
        assert "| only_one |  |  |" in result


class TestExtractMarkdown:
    def test_reads_file(self, tmp_path: Path) -> None:
        md = tmp_path / "test.md"
        md.write_text("# Hello\nworld", encoding="utf-8")
        assert extract_markdown(md) == "# Hello\nworld"


class TestSpecsTomlPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        entries = [
            SpecEntry(
                path="specs/auth.pdf",
                modules=["src/auth/**", "src/middleware/auth_*.py"],
                summary_path="specs/auth.summary.md",
                label="Auth Module",
            ),
            SpecEntry(
                path="specs/protocol.md",
                modules=["src/protocol/"],
                summary_path="specs/protocol.summary.md",
            ),
        ]
        save_specs(tmp_path, entries)

        loaded = load_specs(tmp_path)
        assert len(loaded) == 2

        assert loaded[0].path == "specs/auth.pdf"
        assert loaded[0].modules == ["src/auth/**", "src/middleware/auth_*.py"]
        assert loaded[0].summary_path == "specs/auth.summary.md"
        assert loaded[0].label == "Auth Module"

        assert loaded[1].path == "specs/protocol.md"
        assert loaded[1].modules == ["src/protocol/"]

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        result = load_specs(tmp_path)
        assert result == []

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        save_specs(nested, [SpecEntry(path="test.pdf", modules=["src/"])])
        assert (nested / "specs.toml").exists()


class TestGetSpecContext:
    def test_matches_glob_pattern(self, tmp_path: Path) -> None:
        # Create summary file
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        summary = specs_dir / "auth.summary.md"
        summary.write_text("Auth spec summary content", encoding="utf-8")

        entries = [
            SpecEntry(
                path="specs/auth.pdf",
                modules=["src/auth/**"],
                summary_path="specs/auth.summary.md",
                label="Auth",
            ),
        ]

        result = get_spec_context("src/auth/handler.py", entries, tmp_path)
        assert "Auth" in result
        assert "Auth spec summary content" in result

    def test_no_match(self, tmp_path: Path) -> None:
        entries = [
            SpecEntry(
                path="specs/auth.pdf",
                modules=["src/auth/**"],
                summary_path="specs/auth.summary.md",
            ),
        ]
        result = get_spec_context("src/protocol/parser.py", entries, tmp_path)
        assert result == ""

    def test_multiple_matches(self, tmp_path: Path) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "auth.summary.md").write_text("Auth summary", encoding="utf-8")
        (specs_dir / "security.summary.md").write_text("Security summary", encoding="utf-8")

        entries = [
            SpecEntry(
                path="specs/auth.pdf",
                modules=["src/auth/**"],
                summary_path="specs/auth.summary.md",
                label="Auth",
            ),
            SpecEntry(
                path="specs/security.pdf",
                modules=["src/auth/**", "src/crypto/**"],
                summary_path="specs/security.summary.md",
                label="Security",
            ),
        ]

        result = get_spec_context("src/auth/handler.py", entries, tmp_path)
        assert "Auth summary" in result
        assert "Security summary" in result

    def test_empty_entries(self, tmp_path: Path) -> None:
        result = get_spec_context("src/foo.py", [], tmp_path)
        assert result == ""

    def test_missing_summary_file(self, tmp_path: Path) -> None:
        entries = [
            SpecEntry(
                path="specs/auth.pdf",
                modules=["src/auth/**"],
                summary_path="specs/nonexistent.md",
            ),
        ]
        result = get_spec_context("src/auth/handler.py", entries, tmp_path)
        assert result == ""


class TestGetAllSpecSummaries:
    def test_returns_all(self, tmp_path: Path) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "a.summary.md").write_text("Summary A", encoding="utf-8")
        (specs_dir / "b.summary.md").write_text("Summary B", encoding="utf-8")

        entries = [
            SpecEntry(
                path="specs/a.pdf",
                modules=["src/a/"],
                summary_path="specs/a.summary.md",
                label="Module A",
            ),
            SpecEntry(
                path="specs/b.md",
                modules=["src/b/"],
                summary_path="specs/b.summary.md",
                label="Module B",
            ),
        ]

        result = get_all_spec_summaries(entries, tmp_path)
        assert "Module A" in result
        assert "Summary A" in result
        assert "Module B" in result
        assert "Summary B" in result

    def test_empty_entries(self, tmp_path: Path) -> None:
        result = get_all_spec_summaries([], tmp_path)
        assert result == ""


class TestParseModulesResponse:
    def test_json_object_with_modules(self) -> None:
        text = '{"modules": ["src/auth/**", "src/middleware/"]}'
        result = _parse_modules_response(text)
        assert result == ["src/auth/**", "src/middleware/"]

    def test_json_array(self) -> None:
        text = '["src/auth/**", "src/middleware/"]'
        result = _parse_modules_response(text)
        assert result == ["src/auth/**", "src/middleware/"]

    def test_code_block(self) -> None:
        text = '```json\n{"modules": ["src/core/"]}\n```'
        result = _parse_modules_response(text)
        assert result == ["src/core/"]

    def test_invalid_json(self) -> None:
        text = "some random text"
        result = _parse_modules_response(text)
        assert result == []

    def test_empty_modules(self) -> None:
        text = '{"modules": []}'
        result = _parse_modules_response(text)
        assert result == []
