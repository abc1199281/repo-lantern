"""Claude API adapter."""
import os

from lantern_cli.backends.base import AnalysisResult, BackendAdapter


class ClaudeAdapter(BackendAdapter):
    """Adapter for Anthropic Claude API."""

    def __init__(self, model: str = "claude-3-opus-20240229", api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        """Initialize ClaudeAdapter.

        Args:
            model: Claude model name.
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
        """Analyze a batch of files using Claude API."""
        if not self.health_check():
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")

        # Placeholder for actual API call (e.g., using anthropic lib)
        raw_response = self._call_api(files, context, prompt)
        return self._parse_output(raw_response)

    def synthesize(self, sense_files: list[str], target_language: str) -> str:
        """Synthesize final documentation."""
        return "Synthesis via Claude API not implemented in placeholder."

    def _call_api(self, files: list[str], context: str, prompt: str) -> str:
        """Call Claude API using the SDK."""
        import anthropic
        
        client = anthropic.Anthropic(api_key=os.environ[self.api_key_env])
        
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
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": user_content}
                ]
            )
            return message.content[0].text
        except Exception as e:
            raise RuntimeError(f"Claude API call failed: {str(e)}")

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
            
            # Use same robust parsing logic as GeminiAdapter
            if line.startswith("#") or line.endswith(":"):
                lower_line = line.lower()
                if "summary" in lower_line:
                    current_section = "summary"
                    continue
                elif "insight" in lower_line:
                    current_section = "insights"
                    continue
                elif "question" in lower_line:
                    current_section = "questions"
                    continue
                
            if current_section == "summary":
                if "summary" in line.lower() and len(line) < 20: 
                    continue
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
