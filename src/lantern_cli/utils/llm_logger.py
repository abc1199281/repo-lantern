"""LLM interaction logger for debugging and schema tuning.

Logs every LLM call to a JSONL file with timestamp, prompt/response
previews, token usage, and latency.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default preview length for prompt/response text
_PREVIEW_LEN = 500


class LLMLogger:
    """Append-only JSONL logger for LLM interactions.

    Usage::

        llm_logger = LLMLogger(root_path)
        llm_logger.log(
            caller="runner.run_batch",
            prompt=full_prompt,
            response=raw_output,
            response_obj=response,    # LangChain response for token extraction
        )
    """

    def __init__(self, root_path: Path, output_dir: str = ".lantern") -> None:
        self.log_dir = root_path / output_dir / "logs"
        self.log_path = self.log_dir / "llm_calls.jsonl"

    def log(
        self,
        *,
        caller: str,
        prompt: str,
        response: str,
        response_obj: Any = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Append one interaction record to the JSONL log.

        Args:
            caller: Identifier of the calling function (e.g. ``"runner.run_batch"``).
            prompt: The full prompt text sent to the LLM.
            response: The text response from the LLM.
            response_obj: Optional LangChain response object for token extraction.
            latency_ms: Optional latency in milliseconds.
        """
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None

        if response_obj is not None:
            metadata = getattr(response_obj, "usage_metadata", None)
            if metadata and isinstance(metadata, dict):
                input_tokens = metadata.get("input_tokens")
                output_tokens = metadata.get("output_tokens")

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "caller": caller,
            "prompt_len": len(prompt),
            "response_len": len(response),
            "prompt_preview": prompt[:_PREVIEW_LEN],
            "response_preview": response[:_PREVIEW_LEN],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency_ms) if latency_ms is not None else None,
        }

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"Failed to write LLM log: {exc}")


def timed_invoke(llm: Any, prompt: str) -> tuple[Any, float]:
    """Invoke an LLM and return ``(response, latency_ms)``.

    Convenience wrapper that measures wall-clock time.
    """
    t0 = time.perf_counter()
    response = llm.invoke(prompt)
    latency_ms = (time.perf_counter() - t0) * 1000
    return response, latency_ms
