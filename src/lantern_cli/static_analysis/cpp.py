"""C/C++ static analysis."""
import re
from pathlib import Path


class CppAnalyzer:
    """Analyzer for C/C++ files parsing #include directives."""

    def analyze_imports(self, file_path: Path) -> list[str]:
        """Analyze includes in a C/C++ file.

        Args:
            file_path: Path to the C/C++ file.

        Returns:
            List of included files (e.g., 'iostream', 'utils.h', 'core/config.hpp').
        """
        if not file_path.exists():
            return []

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            return []

        includes = set()

        # Match #include <header> or #include "header"
        # We want to capture the content inside the quotes or brackets
        
        # Regex for #include <...>
        system_includes = re.findall(r'^\s*#\s*include\s+<([^>]+)>', content, re.MULTILINE)
        includes.update(system_includes)

        # Regex for #include "..."
        local_includes = re.findall(r'^\s*#\s*include\s+"([^"]+)"', content, re.MULTILINE)
        includes.update(local_includes)

        return sorted(list(includes))
