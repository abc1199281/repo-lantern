"""Tests for Mermaid diagram validator."""

from lantern_cli.llm.mermaid_validator import (
    _strip_fences,
    _structural_validate,
    clean_and_validate,
)

# ---------------------------------------------------------------------------
# _strip_fences
# ---------------------------------------------------------------------------


class TestStripFences:
    """Tests for fence removal."""

    def test_no_fence_passthrough(self) -> None:
        """Content without fences should pass through unchanged."""
        raw = "graph TD\n    A --> B"
        assert _strip_fences(raw) == raw

    def test_mermaid_fence_removed(self) -> None:
        """```mermaid ... ``` fences should be stripped."""
        raw = "```mermaid\ngraph TD\n    A --> B\n```"
        result = _strip_fences(raw)
        assert result == "graph TD\n    A --> B"
        assert "```" not in result

    def test_plain_fence_removed(self) -> None:
        """Plain ``` ... ``` fences should be stripped."""
        raw = "```\ngraph LR\n    A --> B\n```"
        result = _strip_fences(raw)
        assert "```" not in result
        assert "graph LR" in result

    def test_fence_with_trailing_whitespace(self) -> None:
        """Extra whitespace inside fences should be normalized."""
        raw = "```mermaid\n\ngraph TD\n    A --> B\n\n```  "
        result = _strip_fences(raw)
        assert "```" not in result
        assert "graph TD" in result

    def test_open_fence_no_close(self) -> None:
        """Unclosed fence (truncated LLM output) should be handled."""
        raw = "```mermaid\ngraph TD\n    A --> B"
        result = _strip_fences(raw)
        assert "```" not in result
        assert "graph TD" in result

    def test_lowercase_mermaid_fence(self) -> None:
        """Fence markers are case-insensitive."""
        raw = "```MERMAID\ngraph TD\n    A --> B\n```"
        result = _strip_fences(raw)
        assert "```" not in result
        assert "graph TD" in result


# ---------------------------------------------------------------------------
# _structural_validate
# ---------------------------------------------------------------------------


class TestStructuralValidate:
    """Tests for structural (regex-based) validation."""

    def test_valid_graph_td(self) -> None:
        """graph TD should be valid."""
        assert _structural_validate("graph TD\n    A --> B") is True

    def test_valid_graph_lr(self) -> None:
        """graph LR should be valid."""
        assert _structural_validate("graph LR\n    A --> B") is True

    def test_valid_graph_rl(self) -> None:
        """graph RL should be valid."""
        assert _structural_validate("graph RL\n    A --> B") is True

    def test_valid_graph_tb(self) -> None:
        """graph TB should be valid."""
        assert _structural_validate("graph TB\n    A --> B") is True

    def test_valid_graph_bt(self) -> None:
        """graph BT should be valid."""
        assert _structural_validate("graph BT\n    A --> B") is True

    def test_valid_flowchart_tb(self) -> None:
        """flowchart TB should be valid."""
        assert _structural_validate("flowchart TB\n    A --> B") is True

    def test_valid_sequence_diagram(self) -> None:
        """sequenceDiagram should be valid."""
        content = "sequenceDiagram\n    Alice->>Bob: Hello"
        assert _structural_validate(content) is True

    def test_valid_class_diagram(self) -> None:
        """classDiagram should be valid."""
        content = "classDiagram\n    Animal <|-- Dog : inheritance"
        assert _structural_validate(content) is True

    def test_valid_state_diagram(self) -> None:
        """stateDiagram should be valid."""
        content = "stateDiagram\n    [*] --> Active"
        assert _structural_validate(content) is True

    def test_valid_state_diagram_v2(self) -> None:
        """stateDiagram-v2 should be valid."""
        content = "stateDiagram-v2\n    [*] --> Active"
        assert _structural_validate(content) is True

    def test_valid_er_diagram(self) -> None:
        """erDiagram should be valid."""
        content = "erDiagram\n    CUSTOMER ||--o{ ORDER : places"
        assert _structural_validate(content) is True

    def test_valid_gantt(self) -> None:
        """gantt should be valid."""
        content = "gantt\n    title A Gantt Diagram"
        assert _structural_validate(content) is True

    def test_valid_pie(self) -> None:
        """pie should be valid."""
        content = 'pie\n    title Key elements\n    "Calcium" : 42.96'
        assert _structural_validate(content) is True

    def test_valid_mindmap(self) -> None:
        """mindmap should be valid."""
        content = "mindmap\n    root((mindmap))"
        assert _structural_validate(content) is True

    def test_valid_timeline(self) -> None:
        """timeline should be valid."""
        content = "timeline\n    title History"
        assert _structural_validate(content) is True

    def test_valid_git_graph(self) -> None:
        """gitGraph should be valid."""
        content = "gitGraph\n    commit id: 'A'"
        assert _structural_validate(content) is True

    def test_valid_journey(self) -> None:
        """journey diagram should be valid."""
        content = "journey\n    title My working day"
        assert _structural_validate(content) is True

    def test_empty_string_invalid(self) -> None:
        """Empty string should fail validation."""
        assert _structural_validate("") is False

    def test_whitespace_only_invalid(self) -> None:
        """Whitespace-only string should fail validation."""
        assert _structural_validate("   \n   \n   ") is False

    def test_unknown_type_invalid(self) -> None:
        """Unknown diagram type should fail validation."""
        assert _structural_validate("weirdDiagram\n    A --> B") is False

    def test_graph_missing_direction_invalid(self) -> None:
        """graph without direction should fail validation."""
        assert _structural_validate("graph\n    A --> B") is False

    def test_graph_wrong_direction_invalid(self) -> None:
        """graph with invalid direction should fail validation."""
        assert _structural_validate("graph XX\n    A --> B") is False

    def test_header_only_no_body_invalid(self) -> None:
        """Diagram with only header (no body) should fail."""
        assert _structural_validate("graph TD") is False

    def test_header_only_with_trailing_newline_invalid(self) -> None:
        """Diagram header with newline only should fail."""
        assert _structural_validate("graph TD\n") is False

    def test_prose_text_invalid(self) -> None:
        """Plain prose text should fail validation."""
        assert _structural_validate("This is not a mermaid diagram.") is False

    def test_json_content_invalid(self) -> None:
        """JSON content should fail validation."""
        assert _structural_validate('{"type": "graph", "nodes": []}') is False

    def test_case_insensitive_direction(self) -> None:
        """LLMs sometimes produce lowercase directions like 'graph td'."""
        assert _structural_validate("graph td\n    A --> B") is True

    def test_case_insensitive_keyword(self) -> None:
        """Diagram keywords should be case-insensitive."""
        assert _structural_validate("Graph TD\n    A --> B") is True

    def test_flowchart_lowercase_direction(self) -> None:
        """flowchart with lowercase direction should pass."""
        assert _structural_validate("flowchart lr\n    A --> B") is True


# ---------------------------------------------------------------------------
# clean_and_validate (public API)
# ---------------------------------------------------------------------------


class TestCleanAndValidate:
    """Tests for the public entry point."""

    def test_valid_unfenced_passthrough(self) -> None:
        """Valid unfenced content should pass through unchanged."""
        raw = "graph TD\n    A --> B"
        result = clean_and_validate(raw)
        assert result == raw

    def test_valid_fenced_returns_cleaned(self) -> None:
        """Valid fenced content should be cleaned and returned."""
        raw = "```mermaid\ngraph TD\n    A --> B\n```"
        result = clean_and_validate(raw)
        assert result is not None
        assert "```" not in result
        assert "graph TD" in result

    def test_empty_string_returns_none(self) -> None:
        """Empty string should return None."""
        assert clean_and_validate("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string should return None."""
        assert clean_and_validate("   ") is None

    def test_non_string_returns_none(self) -> None:
        """Non-string input should return None."""
        # clean_and_validate only accepts str; non-str input should return None
        assert clean_and_validate(None) is None  # type: ignore[arg-type]

    def test_invalid_diagram_type_returns_none(self) -> None:
        """Invalid diagram type should return None."""
        assert clean_and_validate("notADiagram\n    A --> B") is None

    def test_graph_missing_direction_returns_none(self) -> None:
        """graph without direction should return None."""
        assert clean_and_validate("graph\n    A --> B") is None

    def test_graph_bad_direction_returns_none(self) -> None:
        """graph with invalid direction should return None."""
        assert clean_and_validate("graph XX\n    A --> B") is None

    def test_header_only_returns_none(self) -> None:
        """Header-only diagram should return None."""
        assert clean_and_validate("graph TD") is None

    def test_prose_returns_none(self) -> None:
        """Plain prose should return None."""
        assert clean_and_validate("The module loads config then starts the server.") is None

    def test_accidentally_fenced_valid_diagram(self) -> None:
        """LLM wraps diagram in fences despite being told not to."""
        raw = "```mermaid\nsequenceDiagram\n    Alice->>Bob: Hi\n    Bob-->>Alice: Hello\n```"
        result = clean_and_validate(raw)
        assert result is not None
        assert "sequenceDiagram" in result
        assert "```" not in result

    def test_double_fenced_edge_case(self) -> None:
        """Paranoid: LLM wraps with extra backtick lines."""
        raw = "```mermaid\ngraph LR\n    A --> B\n```"
        result = clean_and_validate(raw)
        assert result is not None
        assert "graph LR" in result

    def test_all_valid_directions_accepted(self) -> None:
        """All valid directions should be accepted for graph."""
        for direction in ("TD", "TB", "LR", "RL", "BT"):
            raw = f"graph {direction}\n    A --> B"
            result = clean_and_validate(raw)
            assert result is not None, f"Direction {direction} should be valid"

    def test_all_flowchart_directions_accepted(self) -> None:
        """All valid directions should be accepted for flowchart."""
        for direction in ("TD", "TB", "LR", "RL", "BT"):
            raw = f"flowchart {direction}\n    A --> B"
            result = clean_and_validate(raw)
            assert result is not None, f"flowchart {direction} should be valid"

    def test_returns_string_not_none_for_valid(self) -> None:
        """Valid diagram should return string, not None."""
        raw = "classDiagram\n    Animal <|-- Dog : inheritance"
        result = clean_and_validate(raw)
        assert isinstance(result, str)

    def test_leading_whitespace_in_raw_handled(self) -> None:
        """Leading whitespace in raw input should be handled."""
        raw = "\n  graph TD\n    A --> B\n  "
        result = clean_and_validate(raw)
        assert result is not None
        assert "graph TD" in result

    def test_multiple_nodes_graph(self) -> None:
        """Multi-node graph should be valid."""
        raw = "graph TD\n    A --> B\n    B --> C\n    C --> D"
        result = clean_and_validate(raw)
        assert result is not None
        assert "graph TD" in result

    def test_complex_sequence_diagram(self) -> None:
        """Complex sequence diagram should be valid."""
        raw = "sequenceDiagram\n    Alice->>Bob: Hello Bob\n    Bob-->>Alice: Hello Alice"
        result = clean_and_validate(raw)
        assert result is not None


# ---------------------------------------------------------------------------
# Integration: normalize() now uses clean_and_validate
# ---------------------------------------------------------------------------


class TestNormalizeIntegration:
    """Verify that StructuredAnalysisOutput.normalize() calls clean_and_validate."""

    def test_valid_flow_diagram_preserved(self) -> None:
        """Valid flow_diagram should be preserved unchanged."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[],
            language="en",
            flow_diagram="graph TD\n    A --> B",
        )
        assert out.flow_diagram == "graph TD\n    A --> B"

    def test_fenced_flow_diagram_cleaned(self) -> None:
        """Fenced flow_diagram should be cleaned (fences removed)."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[],
            language="en",
            flow_diagram="```mermaid\ngraph TD\n    A --> B\n```",
        )
        assert out.flow_diagram is not None
        assert "```" not in out.flow_diagram
        assert "graph TD" in out.flow_diagram

    def test_invalid_flow_diagram_set_to_none(self) -> None:
        """Invalid flow_diagram should be set to None."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[],
            language="en",
            flow_diagram="This is not valid mermaid",
        )
        assert out.flow_diagram is None

    def test_missing_flow_diagram_stays_none(self) -> None:
        """Missing flow_diagram should stay None (default)."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        out = StructuredAnalysisOutput(summary="s", key_insights=[], language="en")
        assert out.flow_diagram is None

    def test_empty_flow_diagram_set_to_none(self) -> None:
        """Empty flow_diagram should be set to None."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[],
            language="en",
            flow_diagram="   ",
        )
        assert out.flow_diagram is None

    def test_flow_diagram_length_capped_at_2000(self) -> None:
        """flow_diagram longer than 2000 chars should be capped."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        # Build a diagram that exceeds 2000 chars but is structurally valid
        body = "\n".join(f"    N{i} --> N{i+1}" for i in range(300))
        long_diagram = f"graph TD\n{body}"
        out = StructuredAnalysisOutput(
            summary="s",
            key_insights=[],
            language="en",
            flow_diagram=long_diagram,
        )
        # Either truncated to 2000 or None (if truncation broke the body)
        if out.flow_diagram is not None:
            assert len(out.flow_diagram) <= 2000

    def test_diagram_type_keywords_all_supported(self) -> None:
        """All documented diagram types should work."""
        from lantern_cli.llm.structured import StructuredAnalysisOutput

        test_cases = [
            ("graph TD\n    A --> B", True),
            ("flowchart LR\n    A --> B", True),
            ("sequenceDiagram\n    Alice->>Bob: Hi", True),
            ("classDiagram\n    A <|-- B", True),
            ("stateDiagram\n    [*] --> A", True),
            ("stateDiagram-v2\n    [*] --> A", True),
            ("erDiagram\n    A ||--o{ B : has", True),
            ("gantt\n    title A", True),
            ('pie\n    title A\n    "X" : 1', True),
            ("mindmap\n    root((A))", True),
            ("timeline\n    title A", True),
        ]

        for diagram, should_be_valid in test_cases:
            out = StructuredAnalysisOutput(
                summary="s",
                key_insights=[],
                language="en",
                flow_diagram=diagram,
            )
            if should_be_valid:
                assert out.flow_diagram is not None, f"Diagram should be valid: {diagram[:30]}"
            else:
                assert out.flow_diagram is None, f"Diagram should be invalid: {diagram[:30]}"
