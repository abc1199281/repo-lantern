"""TypeScript/JavaScript static analysis."""

import re
from pathlib import Path


class TypeScriptAnalyzer:
    """Analyzer for TypeScript/JavaScript files parsing import statements."""

    def analyze_imports(self, file_path: Path) -> list[str]:
        """Analyze imports in a TypeScript/JavaScript file.

        Args:
            file_path: Path to the TypeScript/JavaScript file.

        Returns:
            List of imported module specifiers (e.g., './utils', 'react', '../config').
        """
        if not file_path.exists():
            return []

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            return []

        imports: set[str] = set()

        # ES module imports: import ... from '...', import '...'
        matches = re.findall(r"import\s+(?:.*from\s+)?['\"]([^'\"]+)['\"]", content)
        imports.update(matches)

        # Re-exports: export ... from '...'
        export_matches = re.findall(r"export\s+(?:.*from\s+)?['\"]([^'\"]+)['\"]", content)
        imports.update(export_matches)

        # CommonJS: require('...')
        require_matches = re.findall(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content)
        imports.update(require_matches)

        return sorted(list(imports))
