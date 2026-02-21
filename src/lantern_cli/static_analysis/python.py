"""Python static analysis using AST."""

import ast
from pathlib import Path


class PythonAnalyzer:
    """Analyzer for Python files using AST."""

    def analyze_imports(self, file_path: Path) -> list[str]:
        """Analyze imports in a Python file.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of imported module names (e.g., 'os', 'pathlib', '.utils').
        """
        if not file_path.exists():
            return []

        try:
            content = file_path.read_text(errors="ignore")
            tree = ast.parse(content)
        except SyntaxError:
            return []
        except Exception:
            return []

        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                level = node.level
                module = node.module or ""
                prefix = "." * level

                if module:
                    # from .utils import x -> .utils
                    # from os import path -> os
                    imports.add(f"{prefix}{module}")
                else:
                    # from . import utils -> .utils
                    # from .. import config -> ..config
                    for alias in node.names:
                        imports.add(f"{prefix}{alias.name}")

        return sorted(list(imports))
