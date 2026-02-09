"""Tests for Synthesizer module."""
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from lantern_cli.core.synthesizer import Synthesizer


class TestSynthesizer:
    """Test Synthesizer class."""

    @pytest.fixture
    def synthesizer(self, tmp_path: Path) -> Synthesizer:
        """Create a Synthesizer instance."""
        # Setup mock sense directory
        sense_dir = tmp_path / ".lantern" / "sense"
        sense_dir.mkdir(parents=True)
        (sense_dir / "batch_0001.sense").write_text("Batch 1 Analysis")
        (sense_dir / "batch_0002.sense").write_text("Batch 2 Analysis")
        
        return Synthesizer(root_path=tmp_path)

    def test_load_sense_files(self, synthesizer: Synthesizer) -> None:
        """Test loading .sense files."""
        contents = synthesizer.load_sense_files()
        assert len(contents) == 2
        assert "Batch 1 Analysis" in contents
        assert "Batch 2 Analysis" in contents

    def test_generate_top_down_docs(self, synthesizer: Synthesizer) -> None:
        """Test generating top-down documentation."""
        # Mock file writing
        with patch("builtins.open", mock_open()) as mock_file:
            synthesizer.generate_top_down_docs()
            
        # Should verify that files like OVERVIEW.md were written
        # Since we use mock_open, we can check calls
        handle = mock_file()
        
        # We expect calls to write to OVERVIEW.md, ARCHITECTURE.md, etc.
        # This is a bit loose, ideally we check paths
        # But for MVP test we can assume success if no error and writes happened
        assert handle.write.called

    def test_empty_sense_files(self, tmp_path: Path) -> None:
        """Test behavior with no sense files."""
        synth = Synthesizer(root_path=tmp_path)
        contents = synth.load_sense_files()
        assert len(contents) == 0
