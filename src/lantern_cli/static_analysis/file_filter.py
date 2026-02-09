"""File filtering logic using pathspec."""
from pathlib import Path
from typing import Generator

import pathspec

from lantern_cli.config.models import FilterConfig


class FileFilter:
    """Filter files based on .gitignore, default rules, and user config."""

    DEFAULT_EXCLUDES = [
        ".git/",
        "node_modules/",
        "vendor/",
        "build/",
        "dist/",
        "__pycache__/",
        "*.min.js",
        "*.map",
        "*.lock",
        "*.pyc",
        ".DS_Store",
        ".venv/",
        ".lantern/",
    ]

    def __init__(self, root_path: Path, config: FilterConfig) -> None:
        """Initialize FileFilter.

        Args:
            root_path: Root directory of the project.
            config: Filter configuration (exclude/include).
        """
        self.root_path = root_path
        self.config = config
        self.gitignore_spec = self._load_gitignore()
        self.default_spec = pathspec.PathSpec.from_lines("gitignore", self.DEFAULT_EXCLUDES)
        self.config_exclude_spec = pathspec.PathSpec.from_lines("gitignore", config.exclude)
        self.config_include_spec = pathspec.PathSpec.from_lines("gitignore", config.include)

    def _load_gitignore(self) -> pathspec.PathSpec | None:
        """Load .gitignore if it exists."""
        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r") as f:
                    return pathspec.PathSpec.from_lines("gitignore", f)
            except Exception:
                pass
        return None

    def should_ignore(self, file_path: Path) -> bool:
        """Check if a file should be ignored.
        
        Priority:
        1. Config Include (Force include) -> Returns False
        2. Config Exclude -> Returns True
        3. Default Exclude -> Returns True
        4. .gitignore -> Returns True
        
        Args:
            file_path: Path to the file (absolute or relative to root).
            
        Returns:
            True if file should be ignored, False otherwise.
        """
        if file_path.is_absolute():
            try:
                rel_path = file_path.relative_to(self.root_path)
            except ValueError:
                # File is not in root path, ignore it (or handle as external)
                # For safety, we ignore files outside root
                return True
        else:
            rel_path = file_path

        rel_str = str(rel_path)

        # 1. Config Include (Force include)
        if self.config_include_spec.match_file(rel_str):
            return False

        # 2. Config Exclude
        if self.config_exclude_spec.match_file(rel_str):
            return True

        # 3. Default Exclude
        if self.default_spec.match_file(rel_str):
            return True

        # 4. .gitignore
        if self.gitignore_spec and self.gitignore_spec.match_file(rel_str):
            return True

        return False

    def walk(self) -> Generator[Path, None, None]:
        """Walk the directory tree and yield valid files.

        Yields:
            Path objects for valid files.
        """
        for path in self.root_path.rglob("*"):
            if path.is_file():
                if not self.should_ignore(path):
                    yield path
