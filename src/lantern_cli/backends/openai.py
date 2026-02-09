"""OpenAI API adapter."""
import os

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


class OpenAIAdapter(BackendAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, model: str = "gpt-4o", api_key_env: str = "OPENAI_API_KEY") -> None:
        """Initialize OpenAIAdapter.

        Args:
            model: OpenAI model name (default: gpt-4o).
            api_key_env: Environment variable for API key (default: OPENAI_API_KEY).
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
        """Analyze a batch of files using OpenAI API."""
        if not self.health_check():
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")

        raw_response = self._call_api(files, context, prompt)
        return self._parse_output(raw_response)

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Synthesize final documentation."""
        return "Synthesis via OpenAI API not implemented in placeholder."

    def _call_api(self, files: list[str], context: str, prompt: str) -> str:
        """Call OpenAI API using the SDK."""
        from openai import OpenAI
        
        client = OpenAI(api_key=os.environ[self.api_key_env])
        
        # Prepare valid message content
        user_content = f"Prompt: {prompt}\n\n"
        
        if context:
            user_content += f"Context:\n{context}\n\n"
            
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    user_content += f"File: {file_path}\n```\n{content}\n```\n\n"
            except Exception as e:
                user_content += f"Error reading {file_path}: {str(e)}\n"

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": user_content}
                ]
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")

    def _parse_output(self, raw_output: str) -> AnalysisResult:
        """Parse LLM response."""
        summary = ""
        insights = []
        questions = []
        current_section = None
        
        lines = raw_output.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Use same robust parsing logic as other adapters
            lower_line = line.lower()
            is_header = False

            if line.startswith("#") or line.endswith(":") or (":" in line and len(line.split(":")[0]) < 20):
                if "summary" in lower_line:
                    current_section = "summary"
                    is_header = True
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            summary += parts[1].strip() + "\n"
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
