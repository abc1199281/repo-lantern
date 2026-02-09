"""Backend Factory for creating LLM adapters."""
import shutil

from lantern_cli.backends.base import BackendAdapter
from lantern_cli.backends.claude import ClaudeAdapter
from lantern_cli.backends.codex import CodexAdapter
from lantern_cli.backends.gemini import GeminiAdapter


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
    def create(config: "LanternConfig") -> BackendAdapter:  # type: ignore
        """Create a backend adapter based on configuration.
        
        Args:
            config: LanternConfig object.
            
        Returns:
            Configured BackendAdapter instance.
        """
        backend_config = config.backend
        
        if backend_config.type == "cli":
            command = backend_config.cli_command or detect_cli()
            return CodexAdapter(
                command=command,
                timeout=backend_config.cli_timeout
            )
        else:
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
            # Add other providers here
            
            raise NotImplementedError(f"API provider '{provider}' not implemented")
