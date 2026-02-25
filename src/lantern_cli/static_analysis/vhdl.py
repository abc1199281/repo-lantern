"""VHDL static analysis."""

import re
from pathlib import Path


class VhdlAnalyzer:
    """Analyzer for VHDL files parsing library and use clauses."""

    def analyze_imports(self, file_path: Path) -> list[str]:
        """Analyze library and use clauses in a VHDL file.

        Args:
            file_path: Path to the VHDL file.

        Returns:
            List of referenced libraries and packages.
        """
        if not file_path.exists():
            return []

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            return []

        deps: set[str] = set()

        # Match: use library.package.item (case-insensitive)
        # e.g. use ieee.std_logic_1164.all;
        #      use work.my_pkg.my_func;
        use_clauses = re.findall(
            r"^\s*use\s+([\w]+)\.([\w]+)", content, re.MULTILINE | re.IGNORECASE
        )
        for library, package in use_clauses:
            lib_lower = library.lower()
            # Skip standard libraries (ieee, std) — they are not project dependencies
            if lib_lower in ("ieee", "std"):
                continue
            # For work library, record just the package name
            if lib_lower == "work":
                deps.add(package.lower())
            else:
                deps.add(f"{lib_lower}.{package.lower()}")

        # Match: component instantiation via entity reference
        # e.g. inst: entity work.alu(rtl)
        entity_refs = re.findall(r"entity\s+([\w]+)\.([\w]+)", content, re.IGNORECASE)
        for library, entity in entity_refs:
            lib_lower = library.lower()
            if lib_lower == "work":
                deps.add(entity.lower())
            else:
                deps.add(f"{lib_lower}.{entity.lower()}")

        return sorted(list(deps))
