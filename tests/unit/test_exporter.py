"""Unit tests for the lantern export module."""

from pathlib import Path

import pytest

from lantern_cli.export.exporter import Exporter
from lantern_cli.export.sidebar import build_sidebar


@pytest.fixture()
def lantern_tree(tmp_path: Path) -> Path:
    """Create a fake .lantern output tree for testing."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    lantern = repo / ".lantern"
    output_en = lantern / "output" / "en"

    # top_down docs
    top_down = output_en / "top_down"
    top_down.mkdir(parents=True)
    (top_down / "OVERVIEW.md").write_text("# Overview\nHello world")
    (top_down / "ARCHITECTURE.md").write_text("# Architecture\nDiagram here")
    (top_down / "CONCEPTS.md").write_text("# Concepts")

    # bottom_up docs
    bottom_up = output_en / "bottom_up" / "src"
    bottom_up.mkdir(parents=True)
    (bottom_up / "main.py.md").write_text("# main.py analysis")
    (bottom_up / "utils.py.md").write_text("# utils.py analysis")

    # lantern_plan.md lives in .lantern/
    (lantern / "lantern_plan.md").write_text("# Plan\n```mermaid\ngraph TD\n```")

    return repo


class TestDocsifyExport:
    def test_basic_export(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        exporter = Exporter(
            repo_path=lantern_tree,
            output_dir=export_dir,
            lang="en",
        )
        result = exporter.export()

        assert result == export_dir
        assert (export_dir / "index.html").exists()
        assert (export_dir / "README.md").exists()
        assert (export_dir / "OVERVIEW.md").exists()
        assert (export_dir / "ARCHITECTURE.md").exists()
        assert (export_dir / "_sidebar.md").exists()
        assert (export_dir / ".nojekyll").exists()

    def test_overview_copied_to_readme(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        readme = (export_dir / "README.md").read_text()
        assert "# Overview" in readme

    def test_dependency_graph_copied(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        dep_graph = export_dir / "dependency-graph.md"
        assert dep_graph.exists()
        assert "mermaid" in dep_graph.read_text()

    def test_bottom_up_preserved(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        assert (export_dir / "bottom_up" / "src" / "main.py.md").exists()
        assert (export_dir / "bottom_up" / "src" / "utils.py.md").exists()

    def test_index_html_contains_repo_name(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        html = (export_dir / "index.html").read_text()
        assert "myrepo" in html

    def test_gitlab_ci_generated(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en", gitlab_ci=True).export()

        ci_file = lantern_tree / ".gitlab-ci.yml"
        assert ci_file.exists()
        assert "pages" in ci_file.read_text()

    def test_gitlab_ci_not_generated_by_default(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        assert not (lantern_tree / ".gitlab-ci.yml").exists()


class TestMkDocsExport:
    def test_mkdocs_export(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "mkdocs_site"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en", fmt="mkdocs").export()

        assert (export_dir / "mkdocs.yml").exists()
        assert (export_dir / "docs" / "index.md").exists()
        assert (export_dir / "docs" / "ARCHITECTURE.md").exists()
        assert (export_dir / "docs" / "dependency-graph.md").exists()

    def test_mkdocs_yml_content(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "mkdocs_site"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en", fmt="mkdocs").export()

        yml = (export_dir / "mkdocs.yml").read_text()
        assert "site_name: myrepo" in yml
        assert "material" in yml
        assert "mermaid2" in yml

    def test_mkdocs_bottom_up(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "mkdocs_site"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en", fmt="mkdocs").export()

        assert (export_dir / "docs" / "bottom_up" / "src" / "main.py.md").exists()


class TestBuildSidebar:
    def test_sidebar_has_home(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        sidebar = build_sidebar(export_dir)
        assert "- [Home](/)" in sidebar

    def test_sidebar_lists_top_level_docs(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        sidebar = build_sidebar(export_dir)
        assert "ARCHITECTURE" in sidebar.upper()

    def test_sidebar_lists_bottom_up(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en").export()

        sidebar = build_sidebar(export_dir)
        assert "Source Files" in sidebar
        assert "main.py" in sidebar.lower()


class TestExportErrors:
    def test_missing_output_dir_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        exporter = Exporter(repo_path=repo, output_dir=tmp_path / "public", lang="en")

        with pytest.raises(FileNotFoundError, match="Lantern output not found"):
            exporter.export()

    def test_idempotent_export(self, lantern_tree: Path, tmp_path: Path) -> None:
        export_dir = tmp_path / "public"
        exporter = Exporter(repo_path=lantern_tree, output_dir=export_dir, lang="en")

        exporter.export()
        exporter.export()  # should not raise

        assert (export_dir / "index.html").exists()
