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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, root_validator

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template" / "bottom_up"


def _load_json(name: str) -> dict[str, Any]:
    with open(TEMPLATE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


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
            values["flow_diagram"] = values["flow_diagram"].strip()[:2000]

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

    def __init__(self, backend: "Backend") -> None:
        self.schema = _load_json("schema.json")
        self.prompts = _load_json("prompts.json")
        self.backend = backend

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

    def analyze_batch(self, items: list[dict[str, str]]) -> list[BatchInteraction]:
        """Run structured analysis in batch via the backend."""
        try:
            responses = self.backend.batch_invoke_structured(
                items,
                self.schema,
                self.prompts,
            )
        except Exception as exc:
            raise RuntimeError(f"Structured batch analysis failed: {exc}") from exc

        outputs: list[BatchInteraction] = []
        for item, response in zip(items, responses, strict=False):
            language = item.get("language", "en")
            raw_text = self._to_text(response)
            parsed = self._parse_output(response, language)
            outputs.append(
                BatchInteraction(
                    prompt_payload=item,
                    raw_response=raw_text,
                    analysis=parsed,
                )
            )
        return outputs

    def analyze(self, file_content: str, language: str) -> StructuredAnalysisOutput:
        """Backward-compatible single-file entrypoint."""
        return self.analyze_batch([{"file_content": file_content, "language": language}])[
            0
        ].analysis
