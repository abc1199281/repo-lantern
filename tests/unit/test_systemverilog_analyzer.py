"""Tests for SystemVerilog static analysis."""

from unittest.mock import MagicMock

from lantern_cli.static_analysis.dependency_graph import DependencyGraph
from lantern_cli.static_analysis.systemverilog import SystemVerilogAnalyzer


def test_sv_analyzer_extracts_includes(tmp_path):
    """Test that SystemVerilogAnalyzer correctly extracts `include directives."""
    sv_file = tmp_path / "top.sv"
    sv_file.write_text(
        '`include "defs.svh"\n' '`include "pkg/utils.vh"\n' "\n" "module top;\n" "endmodule\n"
    )

    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(sv_file)

    assert "defs.svh" in deps
    assert "pkg/utils.vh" in deps
    assert len(deps) == 2


def test_sv_analyzer_extracts_imports(tmp_path):
    """Test that SystemVerilogAnalyzer correctly extracts import statements."""
    sv_file = tmp_path / "top.sv"
    sv_file.write_text(
        "import my_pkg::*;\n" "import another_pkg::some_item;\n" "\n" "module top;\n" "endmodule\n"
    )

    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(sv_file)

    assert "my_pkg" in deps
    assert "another_pkg" in deps
    assert len(deps) == 2


def test_sv_analyzer_mixed_includes_and_imports(tmp_path):
    """Test mixed `include and import extraction."""
    sv_file = tmp_path / "design.sv"
    sv_file.write_text(
        '`include "defs.svh"\n'
        "import bus_pkg::*;\n"
        '`include "macros.vh"\n'
        "import axi_pkg::axi_req_t;\n"
        "\n"
        "module design;\n"
        "endmodule\n"
    )

    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(sv_file)

    assert "defs.svh" in deps
    assert "macros.vh" in deps
    assert "bus_pkg" in deps
    assert "axi_pkg" in deps
    assert len(deps) == 4


def test_sv_analyzer_empty_file(tmp_path):
    """Test that an empty file returns no dependencies."""
    sv_file = tmp_path / "empty.sv"
    sv_file.write_text("")

    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(sv_file)

    assert deps == []


def test_sv_analyzer_nonexistent_file(tmp_path):
    """Test that a non-existent file returns no dependencies."""
    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(tmp_path / "nonexistent.sv")

    assert deps == []


def test_sv_analyzer_deduplicates(tmp_path):
    """Test that duplicate includes/imports are deduplicated."""
    sv_file = tmp_path / "dup.sv"
    sv_file.write_text(
        '`include "defs.svh"\n'
        '`include "defs.svh"\n'
        "import my_pkg::*;\n"
        "import my_pkg::item;\n"
    )

    analyzer = SystemVerilogAnalyzer()
    deps = analyzer.analyze_imports(sv_file)

    assert deps == ["defs.svh", "my_pkg"]


def test_dependency_graph_builds_sv_deps(tmp_path):
    """Test that DependencyGraph correctly builds dependencies for SV files."""
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl/top.sv").write_text('`include "defs.svh"\n`include "alu.sv"\n')
    (tmp_path / "rtl/alu.sv").write_text('`include "defs.svh"\n')
    (tmp_path / "rtl/defs.svh").write_text("")

    mock_filter = MagicMock()
    mock_filter.walk.return_value = [
        tmp_path / "rtl/top.sv",
        tmp_path / "rtl/alu.sv",
        tmp_path / "rtl/defs.svh",
    ]

    graph = DependencyGraph(tmp_path, file_filter=mock_filter)
    graph.build()

    deps = graph.dependencies

    top_node = "rtl/top.sv"
    alu_node = "rtl/alu.sv"
    defs_node = "rtl/defs.svh"

    assert top_node in deps
    assert alu_node in deps[top_node]
    assert defs_node in deps[top_node]

    assert alu_node in deps
    assert defs_node in deps[alu_node]
