"""Generic static analysis module using regex and optional ripgrep."""
import re
import shutil
import subprocess
from pathlib import Path


class GenericAnalyzer:
    """Generic analyzer for extracting imports using regex patterns."""

    def __init__(self) -> None:
        """Initialize the analyzer."""
        self.rg_path = shutil.which("rg")

    def _is_ripgrep_available(self) -> bool:
        """Check if ripgrep is available."""
        return self.rg_path is not None

    def extract_imports(self, file_path: Path, language: str) -> list[str]:
        """Extract imports from a file using regex patterns.

        Args:
            file_path: Path to the file.
            language: Language identifier (python, javascript, etc.).

        Returns:
            List of imported module names.
        """
        if not file_path.exists():
            return []

        content = file_path.read_text(errors="ignore")
        imports = set()

        if language.lower() == "python":
            # import x
            imports.update(re.findall(r"^\s*import\s+([\w\.]+)", content, re.MULTILINE))
            # from x import y
            imports.update(re.findall(r"^\s*from\s+([\w\.]+)\s+import", content, re.MULTILINE))
        
        elif language.lower() in ("javascript", "typescript", "js", "ts"):
            # import x from 'y'
            # import { x } from 'y'
            # import 'y'
            matches = re.findall(r"import\s+(?:.*from\s+)?['\"]([^'\"]+)['\"]", content)
            imports.update(matches)
            
            # const x = require('y')
            matches_require = re.findall(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content)
            imports.update(matches_require)

        return sorted(list(imports))

    def grep_imports(self, directory: Path, pattern: str) -> list[str]:
        """Wrapper for ripgrep to search for patterns in a directory.

        Args:
            directory: Root directory to search.
            pattern: Regex pattern to search.

        Returns:
            List of matching lines/files (simplified).
        """
        if self._is_ripgrep_available():
            try:
                result = subprocess.run(
                    [self.rg_path, pattern, str(directory), "--no-heading", "--line-number"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.splitlines()
            except subprocess.CalledProcessError:
                return []
        else:
            # Fallback to pure Python walk (simplified)
            matches = []
            regex = re.compile(pattern)
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        for i, line in enumerate(file_path.read_text(errors="ignore").splitlines(), 1):
                            if regex.search(line):
                                matches.append(f"{file_path}:{i}:{line}")
                    except Exception:
                        continue
            return matches
