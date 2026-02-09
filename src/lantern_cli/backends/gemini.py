"""Gemini API adapter."""
import os
from typing import Any

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


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

        # Placeholder for actual API call (e.g., using google-generativeai lib)
        # For now, we simulate or wrap logic
        # In real impl, we would construct the prompt with file contents
        
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
            except Exception as e:
                parts.append(f"\nError reading {file_path}: {str(e)}\n")

        try:
            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {str(e)}")

    def _parse_output(self, raw_output: str) -> AnalysisResult:
        """Parse LLM response."""
        summary = ""
        insights = []
        questions = []
        current_section = None
        
        # More robust parsing for Markdown output and legacy Key: Value format
        lines = raw_output.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for headers
            lower_line = line.lower()
            is_header = False
            
            if line.startswith("#") or line.endswith(":") or (":" in line and len(line.split(":")[0]) < 20):
                if "summary" in lower_line:
                    current_section = "summary"
                    is_header = True
                    # If format is "Summary: Value", extract value immediately
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            summary += parts[1].strip() + "\n"
                            # Don't mark as header if it has content, so we don't skip it?
                            # Actually, we extracted content, so we are good.
                elif "insight" in lower_line:
                    current_section = "insights"
                    is_header = True
                elif "question" in lower_line:
                    current_section = "questions"
                    is_header = True
            
            if is_header:
                 continue
                
            if current_section == "summary":
                summary += line + "\n"
            elif current_section == "insights":
                if line.startswith("- ") or line.startswith("* ") or line[0].isdigit():
                    content = line.lstrip("-*1234567890. ")
                    insights.append(content)
            elif current_section == "questions":
                 if line.startswith("- ") or line.startswith("* ") or line[0].isdigit():
                    content = line.lstrip("-*1234567890. ")
                    questions.append(content)
                    
        return AnalysisResult(
            summary=summary.strip(),
            key_insights=insights,
            questions=questions,
            raw_output=raw_output
        )
