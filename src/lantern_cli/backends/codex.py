"""Codex CLI adapter."""
import shutil
import subprocess
from typing import Optional

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


class CodexAdapter(BackendAdapter):
    """Adapter for Codex/Antigravity CLI tools."""

    def __init__(self, command: str = "codex", timeout: int = 300, use_exec: bool = True) -> None:
        """Initialize CodexAdapter.

        Args:
            command: CLI command to use (default: codex).
            timeout: Timeout in seconds (default: 300).
            use_exec: Whether to use 'exec' subcommand (default: True).
        """
        self.command = command
        self.timeout = timeout
        self.use_exec = use_exec

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

        # Construct CLI prompt/input
        if self.use_exec:
            cmd = [self.command, "exec", prompt]
        else:
            cmd = [self.command, prompt]
        
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

    def _parse_output(self, raw_output: str) -> AnalysisResult:
        """Parse raw CLI output into structured result.
        
        Simple parser assuming sections are marked.
        Real implementation would need more robust parsing.
        """
        summary = ""
        insights = []
        questions = []
        
        current_section = None
        
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if "SUMMARY:" in line:
                current_section = "summary"
                continue
            elif "INSIGHTS:" in line:
                current_section = "insights"
                continue
            elif "QUESTIONS:" in line:
                current_section = "questions"
                continue
                
            if current_section == "summary":
                summary += line + "\n"
            elif current_section == "insights":
                if line.startswith("- "):
                    insights.append(line[2:])
            elif current_section == "questions":
                if line.startswith("- "):
                    questions.append(line[2:])
                    
        return AnalysisResult(
            summary=summary.strip(),
            key_insights=insights,
            questions=questions,
            raw_output=raw_output
        )
