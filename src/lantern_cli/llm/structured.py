"""Structured analyzer for bottom-up documentation.

Uses the ``Backend`` protocol for LLM calls instead of LangChain directly.
The LangChain-specific chain logic now lives in ``LangChainBackend``.

Usage example:
    backend = create_backend(config)
    analyzer = StructuredAnalyzer(backend)
    outputs = analyzer.analyze_batch(
        [{"file_content": "def add(a, b): return a + b", "language": "zh-TW"}]
    )
    first = outputs[0]
    print(first.summary)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, root_validator

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "bottom_up"

MERMAID_REPAIR_PROMPT = """\
You are a Mermaid diagram syntax expert. Fix the following invalid diagram.

ORIGINAL (INVALID):
{invalid_diagram}

MERMAID SYNTAX RULES (CRITICAL):
❌ WRONG: graph TD; A[Node]; B[Node]; C[Node];
✅ RIGHT: graph TD
          A[Node]
          B[Node]
          C[Node]
          A --> B
          B --> C

Key rules:
1. NEVER use semicolons (;) — they break Mermaid syntax
2. Each node or connection must be on its own line
3. Start with: graph TD (or flowchart, sequenceDiagram, etc.) — NO SEMICOLON after it
4. Node syntax: A[Label] — wrap labels in [square brackets]
5. Connection syntax: A --> B — use arrows, NOT semicolons
6. Valid directions: TD, TB, LR, RL, BT (for graph/flowchart only)
7. Keep diagram concise (5-8 nodes max)
8. Write node labels in {language}

Output ONLY the corrected raw Mermaid code — no explanations, no fences, no semicolons.
"""


def _load_json(name: str) -> dict[str, Any]:
    with open(TEMPLATE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _repair_truncated_json(text: str) -> str | None:
    """Attempt to close an incomplete JSON object by balancing braces/brackets.

    Walks through the text tracking open braces and brackets while respecting
    string literals, then appends the missing closing tokens.

    Returns:
        Repaired JSON string, or None if the text is not salvageable.
    """
    # Find the first opening brace
    start = text.find("{")
    if start < 0:
        return None

    fragment = text[start:]

    stack: list[str] = []
    in_string = False
    escape = False

    for ch in fragment:
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
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    if not stack:
        # Already balanced — nothing to repair
        return None

    # If we're inside a string, close it first
    if in_string:
        fragment += '"'

    # Close remaining open brackets/braces in reverse order
    close_map = {"{": "}", "[": "]"}
    for opener in reversed(stack):
        fragment += close_map[opener]

    # Quick sanity check: can it parse?
    try:
        json.loads(fragment)
        return fragment
    except json.JSONDecodeError:
        return None


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
        if "```" in text:
            text = text[: text.rfind("```")]
    if text.startswith("{") and text.endswith("}"):
        return text

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
    # Brace walk reached end-of-string — attempt truncated JSON repair
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        logger.warning("Repaired truncated JSON response")
        return repaired
    raise ValueError("Could not extract JSON object from LLM response")


class StructuredAnalysisOutput(BaseModel):
    summary: str = Field(..., max_length=4000)
    key_insights: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    flow: str | None = Field(default=None, max_length=2000)
    flow_diagram: str | None = Field(default=None, max_length=2000)
    references: list[str] = Field(default_factory=list)
    language: str

    @root_validator(pre=True)
    def normalize(cls, values: dict[str, Any]) -> dict[str, Any]:  # noqa: N805
        def trim(items: list[Any], limit: int, item_max: int) -> list[str]:
            cleaned: list[str] = []
            for item in items:
                if not isinstance(item, str):
                    continue
                text = item.strip()
                if text:
                    cleaned.append(text[:item_max])
            return cleaned[:limit]

        values.setdefault("key_insights", [])
        values.setdefault("functions", [])
        values.setdefault("classes", [])
        values.setdefault("references", [])

        values["key_insights"] = trim(values["key_insights"], 8, 400)
        values["functions"] = trim(values["functions"], 5, 400)
        values["classes"] = trim(values["classes"], 5, 400)
        values["references"] = trim(values["references"], 5, 200)

        if "summary" in values and isinstance(values["summary"], str):
            values["summary"] = values["summary"].strip()[:4000]

        if "flow" in values and isinstance(values["flow"], str):
            values["flow"] = values["flow"].strip()[:2000]

        if "flow_diagram" in values and isinstance(values["flow_diagram"], str):
            from lantern_cli.llm.mermaid_validator import clean_and_validate

            validated = clean_and_validate(values["flow_diagram"])
            values["flow_diagram"] = validated[:2000] if validated is not None else None

        if "language" in values and isinstance(values["language"], str):
            values["language"] = values["language"].strip()
        else:
            values["language"] = "en"

        return values


@dataclass
class BatchInteraction:
    prompt_payload: dict[str, str]
    raw_response: str
    analysis: StructuredAnalysisOutput

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt_payload,
            "raw_response": self.raw_response,
            "analysis": self.analysis.model_dump(),
        }


class StructuredAnalyzer:
    """Structured analyzer for bottom-up docs.

    Input contract:
    - `analyze_batch(items)` expects a list of dicts.
    - Each dict should include:
      - `file_content`: source code text
      - `language`: target language code (e.g. `en`, `zh-TW`)

    Output contract:
    - Returns `list[BatchInteraction]` in the same order as input.
    - Each field is normalized to template limits:
      - summary <= 4000 chars
      - flow <= 2000 chars
      - key_insights <= 8, others <= 5

    Error handling:
    - Raises `RuntimeError` when backend invocation fails.
    - Raises `ValueError` when model output cannot be parsed to JSON/object.
    """

    def __init__(self, backend: "Backend", mermaid_repair_retries: int = 2) -> None:
        self.schema = _load_json("schema.json")
        self.prompts = _load_json("prompts.json")
        self.backend = backend
        self.mermaid_repair_retries = mermaid_repair_retries

    @staticmethod
    def _to_payload(response: Any) -> dict[str, Any]:
        if isinstance(response, BaseModel):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            return json.loads(_extract_json(response))
        raise ValueError(f"Unsupported structured response type: {type(response)!r}")

    @staticmethod
    def _to_text(response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, BaseModel):
            return response.model_dump_json()
        if isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False, indent=2)
        return str(response)

    def _parse_output(self, response: Any, language: str) -> StructuredAnalysisOutput:
        payload = self._to_payload(response)
        parsed = StructuredAnalysisOutput.model_validate(payload)
        if not parsed.language:
            parsed.language = language
        return parsed

    def _repair_flow_diagram(self, invalid_diagram: str, language: str) -> str | None:
        """Attempt to repair an invalid Mermaid diagram using the LLM.

        Calls backend.invoke() up to self.mermaid_repair_retries times.
        Returns the first valid repaired diagram, or None if all retries fail.
        """
        from lantern_cli.llm.mermaid_validator import clean_and_validate

        for attempt in range(1, self.mermaid_repair_retries + 1):
            prompt = MERMAID_REPAIR_PROMPT.format(
                invalid_diagram=invalid_diagram,
                language=language,
            )
            try:
                response = self.backend.invoke(prompt)
                candidate = clean_and_validate(response.content)
                if candidate:
                    logger.info(
                        "Mermaid diagram repaired on attempt %d/%d",
                        attempt,
                        self.mermaid_repair_retries,
                    )
                    return candidate
                logger.warning(
                    "Mermaid repair attempt %d/%d produced invalid diagram",
                    attempt,
                    self.mermaid_repair_retries,
                )
            except Exception as exc:
                logger.warning(
                    "Mermaid repair attempt %d/%d failed: %s",
                    attempt,
                    self.mermaid_repair_retries,
                    exc,
                )
        logger.error(
            "All %d Mermaid repair attempts failed; flow_diagram set to None",
            self.mermaid_repair_retries,
        )
        return None

    def analyze_batch(self, items: list[dict[str, str]]) -> list[BatchInteraction]:
        """Run structured analysis in batch via the backend."""
        try:
            responses = self.backend.batch_invoke_structured(
                items,
                self.schema,
                self.prompts,
            )
        except Exception as exc:
            if "length limit" in str(exc).lower() or "length" in str(exc).lower():
                logger.warning(f"Batch hit output length limit, retrying per-file: {exc}")
                return self._analyze_batch_individually(items)
            raise RuntimeError(f"Structured batch analysis failed: {exc}") from exc

        outputs: list[BatchInteraction] = []
        for item, response in zip(items, responses, strict=False):
            language = item.get("language", "en")
            raw_text = self._to_text(response)
            # Peek at the raw flow_diagram before Pydantic normalization drops it
            try:
                raw_payload = self._to_payload(response)
                original_flow_diagram = raw_payload.get("flow_diagram") or ""
            except Exception:
                original_flow_diagram = ""
            parsed = self._parse_output(response, language)
            # If validation rejected the diagram, attempt LLM repair
            if parsed.flow_diagram is None and original_flow_diagram.strip():
                repaired = self._repair_flow_diagram(original_flow_diagram, language)
                if repaired:
                    parsed.flow_diagram = repaired
            outputs.append(
                BatchInteraction(
                    prompt_payload=item,
                    raw_response=raw_text,
                    analysis=parsed,
                )
            )
        return outputs

    def _analyze_batch_individually(self, items: list[dict[str, str]]) -> list[BatchInteraction]:
        """Fallback: analyze each item individually using raw invoke + JSON parsing.

        Bypasses with_structured_output (which is strict about finish_reason)
        and instead parses JSON from raw text, applying truncation repair if needed.
        """
        outputs: list[BatchInteraction] = []
        for item in items:
            language = item.get("language", "en")
            format_item = {"spec_context": "", **item}
            user_prompt = self.prompts.get("user", "").format(**format_item)
            system_prompt = self.prompts.get("system", "")
            full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
            try:
                response = self.backend.invoke(full_prompt)
                raw_text = self._to_text(response)
                # Peek at original flow_diagram before normalization
                try:
                    raw_payload = json.loads(_extract_json(raw_text))
                    original_flow_diagram = raw_payload.get("flow_diagram") or ""
                except Exception:
                    original_flow_diagram = ""
                parsed = self._parse_output(raw_text, language)
                # If validation rejected the diagram, attempt LLM repair
                if parsed.flow_diagram is None and original_flow_diagram.strip():
                    repaired = self._repair_flow_diagram(original_flow_diagram, language)
                    if repaired:
                        parsed.flow_diagram = repaired
                outputs.append(
                    BatchInteraction(
                        prompt_payload=item,
                        raw_response=raw_text,
                        analysis=parsed,
                    )
                )
            except Exception as per_file_exc:
                logger.error(f"Per-file fallback failed: {per_file_exc}")
                fallback = StructuredAnalysisOutput(
                    summary="Analysis failed due to output truncation.",
                    key_insights=[],
                    functions=[],
                    classes=[],
                    flow=None,
                    flow_diagram=None,
                    references=[],
                    language=language,
                )
                outputs.append(
                    BatchInteraction(
                        prompt_payload=item,
                        raw_response=f"error: {per_file_exc}",
                        analysis=fallback,
                    )
                )
        return outputs

    def analyze(self, file_content: str, language: str) -> StructuredAnalysisOutput:
        """Backward-compatible single-file entrypoint."""
        return self.analyze_batch([{"file_content": file_content, "language": language}])[
            0
        ].analysis
