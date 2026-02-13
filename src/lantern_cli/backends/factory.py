"""Backend Factory for creating LLM adapters."""
import shutil
from typing import TYPE_CHECKING, Optional

from lantern_cli.backends.base import BackendAdapter
from lantern_cli.backends.cli import CLIAdapter
from lantern_cli.backends.claude import ClaudeAdapter
from lantern_cli.backends.gemini import GeminiAdapter
from lantern_cli.backends.ollama import OllamaBackend
from lantern_cli.backends.openai import OpenAIAdapter

if TYPE_CHECKING:
    from lantern_cli.config.models import LanternConfig


def detect_cli() -> str:
    """Detect available CLI tool.
    
    Priority:
    1. antigravity
    2. codex
    3. gemini
    4. claude-code (or claude)
    
    Returns:
        Command name of the first found tool.
        
    Raises:
        RuntimeError: If no supported tool is found.
    """
    tools = ["antigravity", "codex", "gemini", "claude"]
    
    for tool in tools:
        if shutil.which(tool):
            return tool
            
    raise RuntimeError("No supported CLI tool found (antigravity, codex, gemini, claude).")


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

        if backend_config.type == "cli":
            command = backend_config.cli_command or detect_cli()
            
            # wrapper logic: set default templates for known tools
            template = backend_config.cli_args_template
            
            if not template:
                if command in ("gemini", "claude", "claude-code"):
                    template = ["{command}", "{prompt}"]
                elif command == "ollama":
                     template = ["{command}", "run", "{model}", "{prompt}"]
                else:
                    # Default for antigravity, codex, and others
                    template = ["{command}", "exec", "{prompt}"]

            return CLIAdapter(
                command=command,
                timeout=backend_config.cli_timeout,
                args_template=template
            )

        elif backend_config.type == "ollama":
            return OllamaBackend(
                model=backend_config.ollama_model or "llama3",
                base_url=backend_config.ollama_url or "http://localhost:11434"
            )

        elif backend_config.type == "api":
            provider = backend_config.api_provider
            model = backend_config.api_model
            api_key = backend_config.api_key_env
            
            if provider == "gemini":
                return GeminiAdapter(
                    model=model or "gemini-1.5-pro",
                    api_key_env=api_key or "GEMINI_API_KEY"
                )
            elif provider in ("claude", "anthropic"):
                return ClaudeAdapter(
                    model=model or "claude-3-opus-20240229",
                    api_key_env=api_key or "ANTHROPIC_API_KEY"
                )
            elif provider in ("openai", "gpt"):
                return OpenAIAdapter(
                    model=model or "gpt-4o",
                    api_key_env=api_key or "OPENAI_API_KEY"
                )
            
            raise NotImplementedError(f"API provider '{provider}' not implemented")

        else:
             raise ValueError(f"Unsupported backend type: {backend_config.type}")
