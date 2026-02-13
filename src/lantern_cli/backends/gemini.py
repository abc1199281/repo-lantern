"""Gemini API adapter."""
import os
import logging
from typing import Any

from lantern_cli.backends.base import AnalysisResult, BackendAdapter

logger = logging.getLogger(__name__)


class GeminiAdapter(BackendAdapter):
    """Adapter for Google Gemini API."""

    def __init__(self, model: str = "gemini-1.5-pro", api_key_env: str = "GEMINI_API_KEY") -> None:
        """Initialize GeminiAdapter.

        Args:
            model: Gemini model name.
            api_key_env: Environment variable for API key.
        """
        self.model = model
        self.api_key_env = api_key_env

    def health_check(self) -> bool:
        """Check if API key is present."""
        return self.api_key_env in os.environ and bool(os.environ[self.api_key_env])

    def analyze_batch(
        self,
        files: list[str],
        context: str,
        prompt: str,
    ) -> AnalysisResult:
        """Analyze a batch of files using Gemini API."""
        if not self.health_check():
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")

        raw_response = self._call_api(files, context, prompt)
        return self._parse_output(raw_response)

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Synthesize final documentation."""
        return "Synthesis via Gemini API not implemented in placeholder."

    def _call_api(self, files: list[str], context: str, prompt: str) -> str:
        """Call Gemini API using the SDK."""
        import google.generativeai as genai
        
        genai.configure(api_key=os.environ[self.api_key_env])
        model = genai.GenerativeModel(self.model)
        
        # Prepare content parts
        parts = []
        if context:
            parts.append(f"Context:\n{context}\n")
            
        parts.append(f"Prompt: {prompt}\n")
        
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    parts.append(f"\nFile: {file_path}\n```\n{content}\n```\n")
            except (FileNotFoundError, UnicodeDecodeError, PermissionError) as e:
                logger.error(f"Failed to read {file_path}: {e}")
                parts.append(f"\nError: Could not read {file_path}\n")
            except Exception as e:
                logger.exception(f"Unexpected error reading {file_path}")
                parts.append(f"\nError reading {file_path}: {str(e)}\n")

        try:
            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {str(e)}")


