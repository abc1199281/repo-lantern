"""Tests for the onboard command."""

from pathlib import Path

from typer.testing import CliRunner

from lantern_cli.cli.main import (
    LANTERN_SECTION_END,
    LANTERN_SECTION_START,
    TOOL_DESTINATIONS,
    app,
)

runner = CliRunner()


class TestOnboard:
    """Test onboard command."""

    def test_creates_all_tool_files(self, tmp_path: Path) -> None:
        """Test that onboard creates files for all tools."""
        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path)])
        assert result.exit_code == 0

        for dest_rel in TOOL_DESTINATIONS.values():
            dest = tmp_path / dest_rel
            assert dest.exists(), f"Expected {dest} to exist"
            content = dest.read_text(encoding="utf-8")
            assert LANTERN_SECTION_START in content
            assert LANTERN_SECTION_END in content

    def test_creates_single_tool_file(self, tmp_path: Path) -> None:
        """Test creating file for a single tool."""
        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "codex"])
        assert result.exit_code == 0

        assert (tmp_path / "AGENTS.md").exists()
        assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_append_to_existing_file(self, tmp_path: Path) -> None:
        """Test that existing content is preserved when appending."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# My Existing Instructions\n\nDo not delete this.\n")

        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "codex"])
        assert result.exit_code == 0

        content = agents_md.read_text(encoding="utf-8")
        assert "# My Existing Instructions" in content
        assert "Do not delete this." in content
        assert LANTERN_SECTION_START in content

    def test_idempotent_skips_existing_section(self, tmp_path: Path) -> None:
        """Test that running twice doesn't duplicate the section."""
        runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "codex"])
        first_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "codex"])
        assert result.exit_code == 0

        second_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert first_content == second_content
        assert "skipped" in result.output

    def test_overwrite_replaces_existing_section(self, tmp_path: Path) -> None:
        """Test that --overwrite replaces the lantern section."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            f"# Header\n\n{LANTERN_SECTION_START}\nold content\n{LANTERN_SECTION_END}\n\n# Footer\n"
        )

        result = runner.invoke(
            app,
            ["onboard", "--repo", str(tmp_path), "--tools", "codex", "--overwrite"],
        )
        assert result.exit_code == 0

        content = agents_md.read_text(encoding="utf-8")
        assert "# Header" in content
        assert "# Footer" in content
        assert "old content" not in content
        assert LANTERN_SECTION_START in content
        assert "replaced" in result.output

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that .github/ directory is created for copilot."""
        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "copilot"])
        assert result.exit_code == 0
        assert (tmp_path / ".github" / "copilot-instructions.md").exists()

    def test_unknown_tool_reports_error(self, tmp_path: Path) -> None:
        """Test that unknown tool names are reported."""
        result = runner.invoke(app, ["onboard", "--repo", str(tmp_path), "--tools", "unknown"])
        assert result.exit_code == 0
        assert "Unknown tool" in result.output
