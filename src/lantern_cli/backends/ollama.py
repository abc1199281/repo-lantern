"""Ollama backend adapter."""

import requests
import json
from lantern_cli.backends.base import BackendAdapter, AnalysisResult

class OllamaBackend(BackendAdapter):
    """Backend adapter for Ollama (local LLMs)."""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        """Initialize OllamaBackend.

        Args:
            model: Model name to use (default: llama3).
            base_url: Base URL for Ollama API (default: http://localhost:11434).
        """
        self.model = model
        self.base_url = base_url.rstrip("/")

    def analyze_batch(
        self,
        files: list[str],
        context: str,
        prompt: str,
    ) -> AnalysisResult:
        """Analyze a batch of files using Ollama."""
        # Check if Ollama is reachable before trying
        if not self.health_check():
             return AnalysisResult(
                summary="Error: Ollama service not reachable",
                raw_output="Could not connect to Ollama service at " + self.base_url
            )

        try:
            raw_response = self._call_api(files, context, prompt)
            return self._parse_output(raw_response)
        except Exception as e:
            return AnalysisResult(
                summary=f"Error calling Ollama: {e}",
                raw_output=str(e)
            )

    def _call_api(self, files: list[str], context: str, prompt: str) -> str:
        """Call Ollama API."""
        import logging
        logger = logging.getLogger(__name__)

        # Construct the full prompt with actual file contents
        full_prompt = f"{prompt}\n\n"

        if context:
            full_prompt += f"Context:\n{context}\n\n"

        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    full_prompt += f"File: {file_path}\n```\n{content}\n```\n\n"
            except (FileNotFoundError, UnicodeDecodeError, PermissionError) as e:
                logger.error(f"Failed to read {file_path}: {e}")
                full_prompt += f"Error: Could not read {file_path}\n\n"
            except Exception as e:
                logger.exception(f"Unexpected error reading {file_path}")
                full_prompt += f"Error reading {file_path}: {str(e)}\n\n"

        full_prompt += """Please analyze the code in these files and provide:
1. A summary of what the code does.
2. Key insights or observations.
3. Any questions or areas that need clarification.
"""

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False
            },
            timeout=300
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")



    def synthesize(
        self,
        sense_files: list[str],
        target_language: str,
    ) -> str:
        """Synthesize final documentation.

        Args:
            sense_files: List of .sense file paths (content not used in this MVP stub).
            target_language: Target language code.

        Returns:
            Synthesized markdown.
        """
        # Placeholder for synthesis logic
        return f"Documentation synthesized by Ollama ({self.model}) for {len(sense_files)} files."

    def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
