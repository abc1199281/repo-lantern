"""SystemVerilog static analysis."""

import re
from pathlib import Path


class SystemVerilogAnalyzer:
    """Analyzer for SystemVerilog files parsing `include and import directives."""

    def analyze_imports(self, file_path: Path) -> list[str]:
        """Analyze includes and imports in a SystemVerilog file.

        Args:
            file_path: Path to the SystemVerilog file.

        Returns:
            List of included files and imported packages.
        """
        if not file_path.exists():
            return []

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            return []

        deps = set()

        # Match `include "filename"
        includes = re.findall(r'^\s*`include\s+"([^"]+)"', content, re.MULTILINE)
        deps.update(includes)

        # Match import package::item or import package::*
        imports = re.findall(r"^\s*import\s+(\w+)::", content, re.MULTILINE)
        deps.update(imports)

        return sorted(list(deps))
