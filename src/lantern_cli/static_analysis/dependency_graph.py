"""Dependency Graph construction and analysis."""
from collections import defaultdict
from pathlib import Path


class DependencyGraph:
    """Graph structure to represent module dependencies."""

    def __init__(self, root_path: Path) -> None:
        """Initialize DependencyGraph.

        Args:
            root_path: Root directory of the project.
        """
        self.root_path = root_path
        # Map: Source -> Set of Targets
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        # Map: Target -> Set of Sources (Reverse graph for some algos)
        self.reverse_dependencies: dict[str, set[str]] = defaultdict(set)

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
