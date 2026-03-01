"""Core exporter — copies docs and renders site templates."""

import shutil
from pathlib import Path

from lantern_cli.export.sidebar import build_sidebar

EXPORT_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "template" / "export"


class Exporter:
    """Packages Lantern output into a deployable static site.

    Args:
        repo_path: Repository root.
        output_dir: Destination directory for the exported site.
        lang: Language code used during analysis.
        lantern_dir: Path to .lantern directory (default: repo_path / ".lantern").
        fmt: Export format — "docsify" or "mkdocs".
        gitlab_ci: Whether to include a .gitlab-ci.yml.
    """

    def __init__(
        self,
        repo_path: Path,
        output_dir: Path,
        lang: str,
        lantern_dir: Path | None = None,
        fmt: str = "docsify",
        gitlab_ci: bool = False,
    ) -> None:
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.lang = lang
        self.lantern_dir = lantern_dir or repo_path / ".lantern"
        self.fmt = fmt
        self.gitlab_ci = gitlab_ci

        self.lantern_output = self.lantern_dir / "output" / self.lang

    def export(self) -> Path:
        """Run the full export pipeline.

        Returns:
            The output directory path.

        Raises:
            FileNotFoundError: If the Lantern output directory does not exist.
        """
        if not self.lantern_output.is_dir():
            raise FileNotFoundError(
                f"Lantern output not found at {self.lantern_output}. "
                "Run 'lantern run' first to generate analysis output."
            )

        if self.fmt == "mkdocs":
            self._export_mkdocs()
        else:
            self._export_docsify()

        return self.output_dir

    def _export_docsify(self) -> None:
        """Export as a Docsify site."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Copy top_down docs
        top_down = self.lantern_output / "top_down"
        if top_down.is_dir():
            for md_file in top_down.glob("*.md"):
                shutil.copy2(md_file, self.output_dir / md_file.name)

        # OVERVIEW.md becomes README.md (Docsify homepage)
        overview = self.output_dir / "OVERVIEW.md"
        readme = self.output_dir / "README.md"
        if overview.exists():
            shutil.copy2(overview, readme)

        # Copy lantern_plan.md as dependency-graph.md
        plan_src = self.lantern_output.parents[1] / "lantern_plan.md"
        if plan_src.exists():
            shutil.copy2(plan_src, self.output_dir / "dependency-graph.md")

        # Copy bottom_up/ tree
        bottom_up_src = self.lantern_output / "bottom_up"
        bottom_up_dst = self.output_dir / "bottom_up"
        if bottom_up_src.is_dir():
            if bottom_up_dst.exists():
                shutil.rmtree(bottom_up_dst)
            shutil.copytree(bottom_up_src, bottom_up_dst)

        # Render index.html
        repo_name = self.repo_path.name
        template_path = EXPORT_TEMPLATE_ROOT / "docsify_index.html"
        html = template_path.read_text(encoding="utf-8")
        html = html.replace("{repo_name}", repo_name)
        (self.output_dir / "index.html").write_text(html, encoding="utf-8")

        # Generate sidebar
        sidebar_content = build_sidebar(self.output_dir)
        (self.output_dir / "_sidebar.md").write_text(sidebar_content, encoding="utf-8")

        # .nojekyll for GitHub Pages
        (self.output_dir / ".nojekyll").write_text("", encoding="utf-8")

        # Optional GitLab CI
        if self.gitlab_ci:
            ci_template = EXPORT_TEMPLATE_ROOT / "gitlab_ci.yml"
            if ci_template.exists():
                shutil.copy2(ci_template, self.repo_path / ".gitlab-ci.yml")

    def _export_mkdocs(self) -> None:
        """Export as an MkDocs site."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        docs_dir = self.output_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Copy top_down docs
        top_down = self.lantern_output / "top_down"
        if top_down.is_dir():
            for md_file in top_down.glob("*.md"):
                shutil.copy2(md_file, docs_dir / md_file.name)

        # OVERVIEW.md becomes index.md (MkDocs homepage)
        overview = docs_dir / "OVERVIEW.md"
        if overview.exists():
            shutil.copy2(overview, docs_dir / "index.md")

        # Copy lantern_plan.md
        plan_src = self.lantern_output.parents[1] / "lantern_plan.md"
        if plan_src.exists():
            shutil.copy2(plan_src, docs_dir / "dependency-graph.md")

        # Copy bottom_up/ tree
        bottom_up_src = self.lantern_output / "bottom_up"
        bottom_up_dst = docs_dir / "bottom_up"
        if bottom_up_src.is_dir():
            if bottom_up_dst.exists():
                shutil.rmtree(bottom_up_dst)
            shutil.copytree(bottom_up_src, bottom_up_dst)

        # Generate mkdocs.yml
        nav = self._build_mkdocs_nav(docs_dir)
        repo_name = self.repo_path.name
        mkdocs_yml = (
            f"site_name: {repo_name}\n"
            f"docs_dir: docs\n"
            f"theme:\n"
            f"  name: material\n"
            f"plugins:\n"
            f"  - search\n"
            f"  - mermaid2\n"
            f"markdown_extensions:\n"
            f"  - toc:\n"
            f"      permalink: true\n"
            f"nav:\n{nav}"
        )
        (self.output_dir / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")

    def _build_mkdocs_nav(self, docs_dir: Path) -> str:
        """Build a YAML nav section for mkdocs.yml.

        Args:
            docs_dir: The docs directory containing all markdown files.

        Returns:
            YAML-formatted nav string.
        """
        lines: list[str] = []

        # index
        if (docs_dir / "index.md").exists():
            lines.append("  - Home: index.md")

        # top-level files
        for md in sorted(docs_dir.glob("*.md")):
            if md.name in ("index.md", "OVERVIEW.md"):
                continue
            title = md.stem.replace("_", " ").replace("-", " ").title()
            lines.append(f"  - {title}: {md.name}")

        # bottom_up subtree
        bottom_up = docs_dir / "bottom_up"
        if bottom_up.is_dir():
            lines.append("  - Source Files:")
            self._walk_mkdocs_nav(bottom_up, docs_dir, lines, depth=3)

        return "\n".join(lines) + "\n"

    def _walk_mkdocs_nav(
        self, directory: Path, docs_dir: Path, lines: list[str], depth: int
    ) -> None:
        """Recursively build MkDocs nav entries.

        Args:
            directory: Current directory.
            docs_dir: Root docs directory for relative path calculation.
            lines: Accumulator for YAML lines.
            depth: Current indentation (in spaces).
        """
        indent = " " * depth
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        for entry in entries:
            if entry.name.startswith(".") or entry.name.startswith("_"):
                continue
            rel = entry.relative_to(docs_dir)
            if entry.is_dir():
                title = entry.name.replace("_", " ").replace("-", " ").title()
                lines.append(f"{indent}- {title}:")
                self._walk_mkdocs_nav(entry, docs_dir, lines, depth + 2)
            elif entry.suffix == ".md":
                title = entry.stem.replace("_", " ").replace("-", " ").title()
                lines.append(f"{indent}- {title}: {rel.as_posix()}")
