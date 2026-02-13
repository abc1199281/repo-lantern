"""Codex CLI adapter."""
import shutil
import subprocess
from typing import Optional

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


class CLIAdapter(BackendAdapter):
    """Adapter for generic CLI tools."""

    def __init__(
        self,
        command: str = "cli",
        timeout: int = 300,
        args_template: list[str] | None = None
    ) -> None:
        """Initialize CLIAdapter.

        Args:
            command: CLI command to use (default: cli).
            timeout: Timeout in seconds (default: 300).
            args_template: Template for arguments.
                           Default is ["{command}", "exec", "{prompt}"].
                           Supported placeholders: {command}, {prompt}.
        """
        self.command = command
        self.timeout = timeout
        self.args_template = args_template or ["{command}", "exec", "{prompt}"]

    def health_check(self) -> bool:
        """Check if CLI tool is available."""
        return shutil.which(self.command) is not None

    def analyze_batch(
        self,
        files: list[str],
        context: str,
        prompt: str,
    ) -> AnalysisResult:
        """Analyze a batch of files using CLI tool."""
        if not self.health_check():
            raise RuntimeError(f"CLI tool '{self.command}' not found.")

        # Construct CLI command from template
        cmd = []
        for arg in self.args_template:
            formatted_arg = arg.format(
                command=self.command,
                prompt=prompt
            )
            cmd.append(formatted_arg)
        
        try:
            # We assume the CLI takes prompt and files and prints output to stdout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True
            )
            return self._parse_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"CLI analysis timed out after {self.timeout}s")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"CLI analysis failed: {e.stderr}")

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Synthesize final documentation."""
        # Placeholder for CLI based synthesis
        return "Synthesis not implemented for CLI backend yet."


