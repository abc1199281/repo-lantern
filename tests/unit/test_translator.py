"""Tests for lantern_cli.core.translator."""

from unittest.mock import MagicMock

import pytest

from lantern_cli.core.translator import Translator
from lantern_cli.llm.backend import LLMResponse


@pytest.fixture
def mock_backend():
    backend = MagicMock()
    backend.invoke.return_value = LLMResponse(content="translated content")
    return backend


@pytest.fixture
def output_dir(tmp_path):
    """Create an output dir with English files already present."""
    en_top = tmp_path / "output" / "en" / "top_down"
    en_top.mkdir(parents=True)
    (en_top / "OVERVIEW.md").write_text("# Overview\nEnglish text.", encoding="utf-8")
    (en_top / "ARCHITECTURE.md").write_text("# Architecture\nEnglish text.", encoding="utf-8")

    en_bottom = tmp_path / "output" / "en" / "bottom_up"
    en_bottom.mkdir(parents=True)
    (en_bottom / "file_a.md").write_text("# File A\nSummary.", encoding="utf-8")

    return tmp_path


def test_skip_when_english(mock_backend, output_dir):
    """translate_all is a no-op when target language is English."""
    translator = Translator(mock_backend, "en", output_dir)
    translator.translate_all()
    mock_backend.invoke.assert_not_called()


def test_translate_top_down_files(mock_backend, output_dir):
    """Top-down .md files are translated and written to target language dir."""
    translator = Translator(mock_backend, "zh-TW", output_dir)
    translator.translate_all()

    dst = output_dir / "output" / "zh-TW" / "top_down"
    assert (dst / "OVERVIEW.md").exists()
    assert (dst / "ARCHITECTURE.md").exists()
    assert (dst / "OVERVIEW.md").read_text(encoding="utf-8") == "translated content"


def test_translate_bottom_up_files(mock_backend, output_dir):
    """Bottom-up .md files are translated and written to target language dir."""
    translator = Translator(mock_backend, "ja", output_dir)
    translator.translate_all()

    dst = output_dir / "output" / "ja" / "bottom_up"
    assert (dst / "file_a.md").exists()
    assert (dst / "file_a.md").read_text(encoding="utf-8") == "translated content"


def test_preserves_directory_structure(mock_backend, tmp_path):
    """Nested directory structure under bottom_up is preserved."""
    nested = tmp_path / "output" / "en" / "bottom_up" / "src" / "core"
    nested.mkdir(parents=True)
    (nested / "runner.md").write_text("# Runner", encoding="utf-8")

    translator = Translator(mock_backend, "ko", tmp_path)
    translator.translate_all()

    dst = tmp_path / "output" / "ko" / "bottom_up" / "src" / "core" / "runner.md"
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "translated content"


def test_handles_missing_source_dir(mock_backend, tmp_path):
    """No crash when English output directories do not exist."""
    translator = Translator(mock_backend, "zh-TW", tmp_path)
    translator.translate_all()  # should not raise
    mock_backend.invoke.assert_not_called()


def test_backend_receives_correct_prompt(mock_backend, output_dir):
    """The prompt sent to the backend includes the target language and content."""
    translator = Translator(mock_backend, "fr", output_dir)
    translator.translate_all()

    # Check that invoke was called and prompt contains the language and content
    assert mock_backend.invoke.call_count > 0
    first_call_prompt = mock_backend.invoke.call_args_list[0][0][0]
    assert "fr" in first_call_prompt
    # The prompt should contain content from one of the English source files
    assert "Summary" in first_call_prompt or "English text" in first_call_prompt
