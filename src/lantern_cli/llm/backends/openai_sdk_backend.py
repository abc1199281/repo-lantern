"""OpenAI SDK backend – uses the ``openai`` Python package directly.

This backend bypasses LangChain and calls the OpenAI Chat Completions API
directly via the ``openai`` package.  It is compatible with the
``openai-agents`` SDK (https://github.com/openai/openai-agents-python) and
any OpenAI-compatible endpoint (OpenRouter, Ollama, vLLM, LiteLLM, etc.)
by accepting a custom ``base_url``.

The same ``openai.OpenAI`` client created here can be reused with the
OpenAI Agents SDK via::

    from agents import set_default_openai_client
    set_default_openai_client(AsyncOpenAI(base_url=..., api_key=...))

This module implements the ``Backend`` protocol so that it can be used as a
drop-in replacement for the LangChain-based backends in the Lantern CLI.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lantern_cli.llm.backend import LLMResponse

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    _OPENAI_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_IMPORT_ERROR = exc


class OpenAISDKBackend:
    """Backend that calls the OpenAI Chat Completions API via the ``openai`` package.

    Supports any OpenAI-compatible endpoint by accepting a custom ``base_url``.
    This makes it usable with OpenRouter, Ollama (OpenAI-compat mode), vLLM,
    LiteLLM proxies, and the OpenAI Agents SDK.

    Example configuration (lantern.toml)::

        [backend]
        type = "openai_sdk"
        openai_sdk_model = "gpt-4o-mini"
        # Optional: point to a different OpenAI-compatible API
        # openai_sdk_base_url = "https://openrouter.ai/api/v1"
        # openai_sdk_api_key_env = "OPENROUTER_API_KEY"
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0,
    ) -> None:
        if OpenAI is None:
            raise RuntimeError(
                "openai package is required. Install it with: pip install openai"
            ) from _OPENAI_IMPORT_ERROR

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self._client = OpenAI(**kwargs)
        self._model = model
        self._temperature = temperature

    # ------------------------------------------------------------------
    # Backend protocol
    # ------------------------------------------------------------------

    def invoke(self, prompt: str) -> LLMResponse:
        """Plain-text generation via OpenAI Chat Completions."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
        )

        message = response.choices[0].message
        content = (message.content or "").strip()

        usage_metadata = None
        if response.usage:
            usage_metadata = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return LLMResponse(content=content, usage_metadata=usage_metadata)

    def batch_invoke_structured(
        self,
        items: list[dict[str, str]],
        json_schema: dict[str, Any],
        prompts: dict[str, str],
    ) -> list[Any]:
        """Structured batch output via OpenAI Chat Completions with JSON mode.

        Sends a system prompt + user prompt per item, requesting JSON output
        that conforms to the given schema.  Uses ``response_format`` when
        available, with a schema-in-prompt fallback for endpoints that do not
        support it.
        """
        results: list[Any] = []

        for item in items:
            try:
                user_prompt = prompts["user"].format(**item)
            except KeyError:
                user_prompt = prompts["user"]

            system_prompt = prompts["system"]

            messages: list[dict[str, str]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Try native JSON schema mode first (OpenAI gpt-4o+ supports this).
            # Fall back to schema-in-prompt for endpoints that reject it.
            parsed = self._invoke_structured_single(messages, json_schema)
            results.append(parsed)

        return results

    @property
    def model_name(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def client(self) -> "OpenAI":
        """Expose the underlying ``openai.OpenAI`` client.

        Useful for callers that want to pass the same client to the OpenAI
        Agents SDK or other libraries.
        """
        return self._client

    def _invoke_structured_single(
        self,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> Any:
        """Invoke a single structured request, trying native JSON schema first."""
        # Strategy 1: response_format with json_schema (OpenAI native)
        try:
            return self._try_native_json_schema(messages, json_schema)
        except Exception as native_err:
            logger.debug(
                f"Native json_schema response_format not supported, "
                f"falling back to schema-in-prompt: {native_err}"
            )

        # Strategy 2: response_format=json_object + schema embedded in prompt
        try:
            return self._try_json_object_mode(messages, json_schema)
        except Exception as json_obj_err:
            logger.debug(
                f"json_object response_format not supported, "
                f"falling back to plain prompt: {json_obj_err}"
            )

        # Strategy 3: plain prompt with schema instruction (most compatible)
        return self._try_plain_prompt(messages, json_schema)

    def _try_native_json_schema(
        self,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Use ``response_format`` with ``json_schema`` type (OpenAI gpt-4o+)."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self._temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("name", "structured_output"),
                    "schema": json_schema.get("parameters", json_schema),
                    "strict": True,
                },
            },
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)

    def _try_json_object_mode(
        self,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Use ``response_format={"type": "json_object"}`` with schema in prompt."""
        schema_instruction = (
            "\n\nYou MUST respond with a JSON object matching this schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
            "Output ONLY the JSON object, no other text."
        )

        augmented_messages = list(messages)
        last = augmented_messages[-1]
        augmented_messages[-1] = {
            **last,
            "content": last["content"] + schema_instruction,
        }

        response = self._client.chat.completions.create(
            model=self._model,
            messages=augmented_messages,  # type: ignore[arg-type]
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)

    def _try_plain_prompt(
        self,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> Any:
        """Most compatible: embed schema in prompt, parse JSON from freeform text."""
        schema_instruction = (
            "\n\nYou MUST respond with a JSON object matching this schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
            "Output ONLY the JSON object, no other text."
        )

        augmented_messages = list(messages)
        last = augmented_messages[-1]
        augmented_messages[-1] = {
            **last,
            "content": last["content"] + schema_instruction,
        }

        response = self._client.chat.completions.create(
            model=self._model,
            messages=augmented_messages,  # type: ignore[arg-type]
            temperature=self._temperature,
        )
        content = (response.choices[0].message.content or "").strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return json.loads(_extract_json(content))


def _extract_json(raw: str) -> str:
    """Extract the first top-level JSON object from *raw*.

    Handles common LLM response patterns:
    - Plain JSON: ``{"key": "value"}``
    - Fenced code blocks: ````json\\n{...}\\n````
    """
    text = raw.strip()

    if text.startswith("```json"):
        text = text[len("```json"):]
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
                return text[start: idx + 1]
    raise ValueError("Could not extract JSON object from response")
