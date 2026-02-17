"""Tests for C/C++ static analysis."""

from unittest.mock import MagicMock

from lantern_cli.static_analysis.cpp import CppAnalyzer
from lantern_cli.static_analysis.dependency_graph import DependencyGraph


def test_cpp_analyzer_extracts_includes(tmp_path):
    """Test that CppAnalyzer correctly extracts includes."""
    cpp_file = tmp_path / "main.cpp"
    cpp_file.write_text("""
#include <iostream>
#include "utils.h"
#include "core/config.hpp"
#include <vector>

int main() {
    return 0;
}
""")

    analyzer = CppAnalyzer()
    includes = analyzer.analyze_imports(cpp_file)

    assert "iostream" in includes
    assert "utils.h" in includes
    assert "core/config.hpp" in includes
    assert "vector" in includes
    assert len(includes) == 4


def test_dependency_graph_builds_cpp_deps(tmp_path):
    """Test that DependencyGraph correctly builds dependencies for C++ files."""
    # Create a mock project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.cpp").write_text('#include "utils.h"\n#include "core.hpp"')
    (tmp_path / "src/utils.h").write_text('#include "core.hpp"')
    (tmp_path / "src/core.hpp").write_text("")

    # Create mock file_filter that returns the files
    mock_filter = MagicMock()
    mock_filter.walk.return_value = [
        tmp_path / "src/main.cpp",
        tmp_path / "src/utils.h",
        tmp_path / "src/core.hpp",
    ]

    graph = DependencyGraph(tmp_path, file_filter=mock_filter)
    graph.build()

    deps = graph.dependencies

    # Check dependencies
    # Paths are relative to tmp_path
    main_node = "src/main.cpp"
    utils_node = "src/utils.h"
    core_node = "src/core.hpp"

    assert main_node in deps
    assert utils_node in deps[main_node]
    assert core_node in deps[main_node]

    assert utils_node in deps
    assert core_node in deps[utils_node]


"""
def test_dependency_graph_mixed_languages(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("import utils")
    (tmp_path / "src/utils.py").write_text("")
    (tmp_path / "src/core.cpp").write_text('#include "header.h"')
    (tmp_path / "src/header.h").write_text("")

    graph = DependencyGraph(tmp_path, file_filter=MagicMock())
    graph.build()

    deps = graph.dependencies

    # Python deps
    assert "src/main.py" in deps
    assert "src/utils.py" in deps["src/main.py"]

    # C++ deps
    assert "src/core.cpp" in deps
    assert "src/header.h" in deps["src/core.cpp"]
"""
