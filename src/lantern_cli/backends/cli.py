import logging
import shutil
import subprocess
from typing import Optional

from lantern_cli.backends.base import AnalysisResult, BackendAdapter

logger = logging.getLogger(__name__)


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
                           Default is ["{command}", "-p", "{prompt}"].
                           Supported placeholders: {command}, {prompt}.
        """
        self.command = command
        self.timeout = timeout
        self.args_template = args_template or ["{command}", "-p", "{prompt}"]

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
            
            # Log output for debugging
            if result.stdout:
                logger.debug(f"CLI stdout: {result.stdout[:200]}...") # Log first 200 chars
            if result.stderr:
                logger.warning(f"CLI stderr: {result.stderr}")

            # Check for critical errors in stdout/stderr even if exit code is 0
            # Some tools (like codex) might print errors to stdout or stderr but exit 0
            combined_output = (result.stdout + result.stderr).lower()
            
            critical_keywords = ["401 unauthorized", "failed to refresh token", "unauthorized access"]
            
            if any(k in combined_output for k in critical_keywords):
                 raise RuntimeError(
                    f"CLI analysis failed with potential authentication error in output.\n"
                    f"Output snippet: {result.stderr or result.stdout[:200]}\n"
                    f"Hint: Check if you are logged in to '{self.command}' or if your API token is valid."
                 )

            return self._parse_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"CLI analysis timed out after {self.timeout}s")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            
            # Check for common authentication errors
            auth_keywords = ["401", "unauthorized", "token", "auth", "login"]
            if any(keyword in error_msg.lower() for keyword in auth_keywords):
                raise RuntimeError(
                    f"CLI analysis failed with potential authentication error: {error_msg}\n"
                    f"Hint: Check if you are logged in to '{self.command}' or if your API token is valid."
                )
            
            raise RuntimeError(f"CLI analysis failed: {error_msg}")

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Synthesize final documentation."""
        # Placeholder for CLI based synthesis
        return "Synthesis not implemented for CLI backend yet."


