"""Backend Factory for creating LLM adapters."""
import shutil
from typing import TYPE_CHECKING, Optional

from lantern_cli.backends.base import BackendAdapter
from lantern_cli.backends.ollama import OllamaBackend

class BackendFactory:
    """Factory for creating backend adapters."""

    @staticmethod
    def create(config: "LanternConfig") -> BackendAdapter:
        """Create a backend adapter based on configuration.

        Args:
            config: LanternConfig object.

        Returns:
            Configured BackendAdapter instance.
        """
        backend_config = config.backend

        if backend_config.type == "ollama":
            return OllamaBackend(
                model=backend_config.ollama_model or "llama3",
                base_url=backend_config.ollama_url or "http://localhost:11434"
            )

        elif backend_config.type == "api":                        
            raise NotImplementedError(f"API provider not implemented")

        else:
             raise ValueError(f"Unsupported backend type: {backend_config.type}")
