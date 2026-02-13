"""Tests for MemoryManager."""
from unittest.mock import MagicMock

import pytest

from lantern_cli.backends.base import AnalysisResult
from lantern_cli.core.memory_manager import MemoryManager


class TestMemoryManager:
    """Test MemoryManager class."""

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        """Mock backend adapter."""
        backend = MagicMock()
        # Setup default response for analyze_batch (used for compression)
        # Must be > 100 chars to pass validation in MemoryManager
        long_summary = "Compressed summary " * 6  # 19 chars * 6 = 114 chars
        backend.invoke.return_value = long_summary
        return backend

    def test_update_summary_no_compression(self, mock_backend) -> None:
        """Test update without compression when under threshold."""
        manager = MemoryManager(backend=mock_backend)
        manager.COMPRESS_THRESHOLD = 100
        
        current = "Old summary"
        new_content = "New content"
        
        updated = manager.update_summary(current, new_content)
        
        assert updated == "Old summary\n\nNew content"
        mock_backend.analyze_batch.assert_not_called()

    def test_update_summary_compression(self, mock_backend) -> None:
        """Test compression when exceeding threshold."""
        manager = MemoryManager(backend=mock_backend)
        manager.COMPRESS_THRESHOLD = 10  # Low threshold to trigger compression
        
        current = "A" * 20
        new_content = "B" * 20
        
        # Should trigger compression
        updated = manager.update_summary(current, new_content)
        
        expected = ("Compressed summary " * 6).strip()
        assert updated == expected
        mock_backend.invoke.assert_called_once()
        assert manager.compression_count == 1

    def test_compression_fallback(self, mock_backend) -> None:
        """Test fallback truncation when compression fails."""
        manager = MemoryManager(backend=mock_backend)
        manager.COMPRESS_THRESHOLD = 20
        
        # Simulate backend failure
        mock_backend.invoke.side_effect = Exception("API Error")
        
        current = "A" * 50
        new_content = "B" * 50
        
        # Should fall back to tail truncation
        updated = manager.update_summary(current, new_content)
        
        assert updated.startswith("...")
        # Should keep last (20-3) = 17 chars
        assert len(updated) == 20
        assert manager.compression_count == 0

    def test_no_backend_fallback(self) -> None:
        """Test fallback when no backend provided."""
        manager = MemoryManager(backend=None)
        manager.COMPRESS_THRESHOLD = 20
        
        current = "A" * 50
        new_content = "B" * 50
        
        updated = manager.update_summary(current, new_content)
        
        assert updated.startswith("...")
        assert len(updated) == 20
