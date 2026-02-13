"""Dependency Graph construction and analysis."""
from collections import defaultdict
from pathlib import Path


class DependencyGraph:
    """Graph structure to represent module dependencies."""

    def __init__(self, root_path: Path, excludes: list[str] = None) -> None:
        """Initialize DependencyGraph.

        Args:
            root_path: Root directory of the project.
            excludes: List of glob patterns to exclude.
        """
        self.root_path = root_path
        self.excludes = excludes or []
        
        # Map: Source -> Set of Targets
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        # Map: Target -> Set of Sources (Reverse graph for some algos)
        self.reverse_dependencies: dict[str, set[str]] = defaultdict(set)
        
        # Lazy import to avoid circular dependency
        from lantern_cli.static_analysis.python import PythonAnalyzer
        from lantern_cli.static_analysis.cpp import CppAnalyzer
        from pathspec import PathSpec
        from pathspec.patterns import GitWildMatchPattern
        
        self.analyzers = {
            "python": PythonAnalyzer(),
            "cpp": CppAnalyzer(),
        }
        self.spec = PathSpec.from_lines(GitWildMatchPattern, self.excludes)

    def build(self) -> None:
        """Build the dependency graph by analyzing files in root_path."""
        # 1. Index all files
        module_map: dict[str, str] = {}
        all_files: list[tuple[Path, str]] = []  # (rel_path, type)
        
        # Extensions mapping
        extensions = {
            ".py": "python",
            ".c": "cpp",
            ".cpp": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".hh": "cpp",
            ".cxx": "cpp",
            ".hxx": "cpp",
        }

        # Walk excluding hidden/venv etc. AND user defined excludes
        # We need to walk all files now, not just .py
        for path in self.root_path.rglob("*"):
            if not path.is_file():
                continue

            # Check extension
            ext = path.suffix.lower()
            if ext not in extensions:
                continue

            rel_path = path.relative_to(self.root_path)
            
            # 1. Basic hardcoded Clean check (use repository-relative parts)
            # Use `rel_path.parts` so ancestor directories (e.g. /.../.openclaw/...) don't cause all files to be skipped.
            if any(part.startswith(".") or part == "__pycache__" or part == "venv" or part == "node_modules" for part in rel_path.parts):
                continue
            
            # 2. Config based Check
            if self.spec.match_file(str(rel_path)):
                continue
            
            file_type = extensions[ext]
            all_files.append((rel_path, file_type))
            
            if file_type == "python":
                # Simple module name heuristic
                # src/lantern_cli/main.py -> src.lantern_cli.main
                module_parts = list(rel_path.parent.parts) + [rel_path.stem]
                module_name = ".".join(module_parts)
                module_map[module_name] = str(rel_path)
                
                # Also support implicit src root if common pattern
                if module_parts[0] == "src":
                    short_name = ".".join(module_parts[1:])
                    module_map[short_name] = str(rel_path)
            elif file_type == "cpp":
                # For C++, we map filename (e.g. "utils.h") to path
                # And also relative paths if possible
                module_map[path.name] = str(rel_path)
                # Map full relative path for precise includes
                module_map[str(rel_path)] = str(rel_path)

        # 2. Analyze imports and build graph
        for rel_path, file_type in all_files:
            file_path = self.root_path / rel_path
            
            analyzer = self.analyzers.get(file_type)
            if not analyzer:
                continue

            imports = analyzer.analyze_imports(file_path)
            
            source_node = str(rel_path)
            # Ensure node exists in graph even if no deps
            if source_node not in self.dependencies:
                self.dependencies[source_node] = set()

            for imp in imports:
                target_file = None
                
                if file_type == "python":
                    # Try to resolve import to a file in our project
                    target_file = module_map.get(imp)
                    
                    # Try sub-modules (e.g. import lantern_cli.core -> lantern_cli/core/__init__.py)
                    if not target_file:
                        target_file = module_map.get(f"{imp}.__init__")
                
                elif file_type == "cpp":
                    # Direct lookup by filename or path
                    target_file = module_map.get(imp)
                    
                    # If not found, try to resolve relative paths
                    if not target_file:
                        # Handle "../utils.h" style includes if needed, 
                        # but simple name matching covers many cases in flat/simple C++ projects
                        pass

                if target_file and target_file != source_node:
                    self.add_dependency(source_node, target_file)

    def add_dependency(self, source: str, target: str) -> None:
        """Add a dependency: source depends on target.

        Args:
            source: Source module name.
            target: Target module name.
        """
        self.dependencies[source].add(target)
        self.reverse_dependencies[target].add(source)

    def calculate_layers(self) -> dict[str, int]:
        """Calculate the 'level' of each module.
        
        Level 0: No outgoing dependencies (Leaf nodes).
        Level N: Max level of dependencies + 1.
        
        Returns:
            Dict mapping module name to its level.
        """
        levels: dict[str, int] = {}
        processed = set()
        
        # Modules with no dependencies are level 0
        all_modules = set(self.dependencies.keys()) | set(self.reverse_dependencies.keys())
        
        # Iterative calculation (simple approach for DAGs)
        # Limitation: Circular dependencies might cause infinite loop or incorrect levels if not handled.
        # For MVP, we ignore cycles in level calculation or cap iterations.
        
        # Initialize leaves
        for module in all_modules:
            if not self.dependencies[module]:
                levels[module] = 0
                processed.add(module)
        
        changed = True
        max_iter = len(all_modules) + 2
        iter_count = 0
        
        while changed and iter_count < max_iter:
            changed = False
            iter_count += 1
            
            for module in all_modules:
                if module in levels:
                    continue
                
                # Check if all dependencies have levels calculated
                deps = self.dependencies[module]
                if all(d in levels for d in deps):
                    max_dep_level = max(levels[d] for d in deps)
                    levels[module] = max_dep_level + 1
                    changed = True
        
        # Assign -1 or max+1 for modules in cycles that couldn't be resolved
        for module in all_modules:
            if module not in levels:
                levels[module] = -1  # Indication of cycle participation or unresolved
                
        return levels

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies using DFS.

        Returns:
            List of cycles (each cycle is a list of module names).
        """
        cycles = []
        visited = set()
        recursion_stack = set()
        path = []

        def dfs(node: str):
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)

            for neighbor in self.dependencies[node]:
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in recursion_stack:
                    # Cycle found
                    # Extract cycle path
                    try:
                        idx = path.index(neighbor)
                        cycles.append(path[idx:] + [neighbor])
                    except ValueError:
                        pass # Should not happen

            recursion_stack.remove(node)
            path.pop()

        for node in list(self.dependencies.keys()):
            if node not in visited:
                dfs(node)

        return cycles
