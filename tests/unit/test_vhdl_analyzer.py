"""Tests for VHDL static analysis."""

from unittest.mock import MagicMock

from lantern_cli.static_analysis.dependency_graph import DependencyGraph
from lantern_cli.static_analysis.vhdl import VhdlAnalyzer


def test_vhdl_analyzer_extracts_use_clauses(tmp_path):
    """Test that VhdlAnalyzer correctly extracts use clauses."""
    vhdl_file = tmp_path / "top.vhd"
    vhdl_file.write_text(
        "library ieee;\n"
        "use ieee.std_logic_1164.all;\n"
        "use ieee.numeric_std.all;\n"
        "\n"
        "library work;\n"
        "use work.my_pkg.all;\n"
        "use work.util_pkg.some_func;\n"
        "\n"
        "entity top is\n"
        "end entity top;\n"
    )

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    # ieee should be excluded (standard library)
    assert "my_pkg" in deps
    assert "util_pkg" in deps
    assert len(deps) == 2


def test_vhdl_analyzer_extracts_entity_references(tmp_path):
    """Test that VhdlAnalyzer correctly extracts entity instantiations."""
    vhdl_file = tmp_path / "top.vhd"
    vhdl_file.write_text(
        "architecture rtl of top is\n"
        "begin\n"
        "  u_alu: entity work.alu(rtl)\n"
        "    port map (a => a, b => b);\n"
        "end architecture rtl;\n"
    )

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert "alu" in deps
    assert len(deps) == 1


def test_vhdl_analyzer_mixed_use_and_entity(tmp_path):
    """Test mixed use clauses and entity references."""
    vhdl_file = tmp_path / "design.vhd"
    vhdl_file.write_text(
        "library ieee;\n"
        "use ieee.std_logic_1164.all;\n"
        "use work.bus_pkg.all;\n"
        "\n"
        "architecture rtl of design is\n"
        "begin\n"
        "  u_ctrl: entity work.controller(behav)\n"
        "    port map (clk => clk);\n"
        "end architecture rtl;\n"
    )

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert "bus_pkg" in deps
    assert "controller" in deps
    assert len(deps) == 2


def test_vhdl_analyzer_custom_library(tmp_path):
    """Test that non-standard, non-work libraries are captured with library prefix."""
    vhdl_file = tmp_path / "top.vhd"
    vhdl_file.write_text("use mylib.my_component.all;\n")

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert "mylib.my_component" in deps
    assert len(deps) == 1


def test_vhdl_analyzer_empty_file(tmp_path):
    """Test that an empty file returns no dependencies."""
    vhdl_file = tmp_path / "empty.vhd"
    vhdl_file.write_text("")

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert deps == []


def test_vhdl_analyzer_nonexistent_file(tmp_path):
    """Test that a non-existent file returns no dependencies."""
    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(tmp_path / "nonexistent.vhd")

    assert deps == []


def test_vhdl_analyzer_deduplicates(tmp_path):
    """Test that duplicate references are deduplicated."""
    vhdl_file = tmp_path / "dup.vhd"
    vhdl_file.write_text(
        "use work.my_pkg.all;\n" "use work.my_pkg.some_func;\n" "use work.other_pkg.all;\n"
    )

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert deps == ["my_pkg", "other_pkg"]


def test_vhdl_analyzer_case_insensitive(tmp_path):
    """Test that VHDL keywords are handled case-insensitively."""
    vhdl_file = tmp_path / "mixed_case.vhd"
    vhdl_file.write_text("USE Work.My_Pkg.ALL;\n" "Use WORK.Other_Pkg.Some_Func;\n")

    analyzer = VhdlAnalyzer()
    deps = analyzer.analyze_imports(vhdl_file)

    assert "my_pkg" in deps
    assert "other_pkg" in deps
    assert len(deps) == 2


def test_dependency_graph_builds_vhdl_deps(tmp_path):
    """Test that DependencyGraph correctly builds dependencies for VHDL files."""
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl/top.vhd").write_text("use work.alu.all;\n" "use work.my_pkg.all;\n")
    (tmp_path / "rtl/alu.vhd").write_text("use work.my_pkg.all;\n")
    (tmp_path / "rtl/my_pkg.vhd").write_text("library ieee;\n" "use ieee.std_logic_1164.all;\n")

    mock_filter = MagicMock()
    mock_filter.walk.return_value = [
        tmp_path / "rtl/top.vhd",
        tmp_path / "rtl/alu.vhd",
        tmp_path / "rtl/my_pkg.vhd",
    ]

    graph = DependencyGraph(tmp_path, file_filter=mock_filter)
    graph.build()

    deps = graph.dependencies

    top_node = "rtl/top.vhd"
    alu_node = "rtl/alu.vhd"
    pkg_node = "rtl/my_pkg.vhd"

    assert top_node in deps
    assert alu_node in deps[top_node]
    assert pkg_node in deps[top_node]

    assert alu_node in deps
    assert pkg_node in deps[alu_node]
