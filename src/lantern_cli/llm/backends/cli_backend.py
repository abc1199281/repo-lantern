"""CLI backend – invokes an external CLI tool as the LLM.

Executes a command via subprocess and passes the prompt via stdin.
The stdout is parsed as the model response. Structured output is
achieved by embedding the JSON schema in the prompt and parsing the
returned JSON.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from lantern_cli.llm.backend import LLMResponse

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> str:
    """Extract the first top-level JSON object from *raw*.

    Handles common LLM response patterns:
    - Plain JSON: ``{"key": "value"}``
    - Fenced code blocks: ````json\\n{...}\\n````

    Raises:
        ValueError: If no JSON object can be found.
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```json"):
        text = text[len("```json") :]
        if "```" in text:
            text = text[: text.rfind("```")]
    if text.startswith("{") and text.endswith("}"):
        return text

    # Walk the string looking for balanced braces
    depth = 0
    start = None
    in_string = False
    escape = False
    for idx, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{" and start is None:
            start = idx
        if ch == "{" and start is not None:
            depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise ValueError("Could not extract JSON object from CLI response")


class CLIBackend:
    """Backend that shells out to a CLI tool for LLM inference.

    Example configuration (lantern.toml)::

        [backend]
        type = "cli"
        cli_command = "llm -m gpt-4o-mini"
        cli_model_name = "gpt-4o-mini"

    The CLI tool must accept prompts via stdin and write responses to stdout.
    Usage metadata is not available from CLI tools, so
    ``LLMResponse.usage_metadata`` always carries zero counts.
    """

    def __init__(
        self,
        command: list[str],
        model: str = "cli",
        timeout: int = 300,
    ) -> None:
        """Initialise with the CLI command tokens.

        Args:
            command: Command list, e.g. ``["codex", "exec"]``.
            model: Display name for cost tracking.
            timeout: Maximum seconds to wait for each subprocess call.
        """
        self._command = command
        self._model = model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, prompt: str) -> str:
        """Execute the CLI command with *prompt* via stdin and return stdout."""
        try:
            result = subprocess.run(
                self._command,
                input=prompt,
                capture_output=True,
                text=True,
                check=True,
                timeout=self._timeout,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or ""
            raise RuntimeError(
                f"CLI command failed (exit {exc.returncode}): {stderr[:500]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"CLI command timed out after {self._timeout}s") from exc

    @staticmethod
    def _zero_usage() -> dict[str, int]:
        """Return a zero-count usage metadata dict."""
        return {"input_tokens": 0, "output_tokens": 0}

    # ------------------------------------------------------------------
    # Backend protocol
    # ------------------------------------------------------------------

    def invoke(self, prompt: str) -> LLMResponse:
        """Plain-text generation via CLI."""
        content = self._run(prompt)
        return LLMResponse(content=content, usage_metadata=self._zero_usage())

    def batch_invoke_structured(
        self,
        items: list[dict[str, str]],
        json_schema: dict[str, Any],
        prompts: dict[str, str],
    ) -> list[Any]:
        """Structured batch output via CLI.

        For each item the system and user prompts are formatted, the
        JSON schema requirement is appended, and the CLI tool is invoked.
        The raw stdout is then parsed as JSON.

        CLI tools do not support native batch operations, so this is
        implemented as sequential calls.
        """
        schema_instruction = (
            "\n\nYou MUST respond with a JSON object matching this schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
            "Output ONLY the JSON object, no other text."
        )

        results: list[Any] = []
        for item in items:
            try:
                user_prompt = prompts["user"].format(**item)
            except KeyError:
                user_prompt = prompts["user"]

            full_prompt = f"{prompts['system']}\n\n{user_prompt}{schema_instruction}"
            raw = self._run(full_prompt)

            try:
                parsed = json.loads(_extract_json(raw))
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Failed to parse structured CLI response: {exc}. "
                    f"Returning raw string for downstream handling."
                )
                parsed = raw

            results.append(parsed)

        return results

    @property
    def model_name(self) -> str:
        return self._model
