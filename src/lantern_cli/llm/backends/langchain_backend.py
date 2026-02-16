"""LangChain backend – wraps a LangChain ChatModel behind the Backend protocol.

All LangChain-specific imports (ChatPromptTemplate, RunnableLambda,
with_structured_output) are confined to this module.  The rest of the
codebase depends only on the ``Backend`` protocol defined in
``llm.backend``.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from lantern_cli.llm.backend import LLMResponse

logger = logging.getLogger(__name__)


class LangChainBackend:
    """Backend implementation that delegates to a LangChain ChatModel.

    Wraps the three operations consumed by the application:

    * ``invoke`` – plain text generation via ``ChatModel.invoke()``
    * ``batch_invoke_structured`` – structured batch output via
      ``ChatModel.with_structured_output()`` + ``Runnable.batch()``
    * ``model_name`` – passthrough of the model identifier
    """

    def __init__(self, chat_model: Any, model: str = "unknown") -> None:
        """Initialise with a LangChain ChatModel instance.

        Args:
            chat_model: A LangChain ``BaseChatModel`` instance (e.g.
                ``ChatOpenAI``, ``ChatOllama``).
            model: Human-readable model name for cost tracking.
        """
        self._llm = chat_model
        self._model = model

    # ------------------------------------------------------------------
    # Backend protocol
    # ------------------------------------------------------------------

    def invoke(self, prompt: str) -> LLMResponse:
        """Plain-text generation."""
        response = self._llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        content = str(content).strip()
        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(content=content, usage_metadata=usage)

    def batch_invoke_structured(
        self,
        items: list[dict[str, str]],
        json_schema: dict[str, Any],
        prompts: dict[str, str],
    ) -> list[Any]:
        """Structured batch output via LangChain chain.

        Replicates the logic previously in ``llm.structured.create_chain``:
        builds a ``ChatPromptTemplate``, applies ``with_structured_output``,
        and runs ``.batch()`` over all *items*.
        """
        prompt_tpl = ChatPromptTemplate.from_messages(
            [("system", prompts["system"]), ("user", prompts["user"])]
        )
        structured_llm = self._llm.with_structured_output(json_schema)

        def _runner(inp: Any) -> Any:
            if isinstance(inp, dict):
                prompt_value = prompt_tpl.format_prompt(**inp)
                return structured_llm.invoke(prompt_value)
            return structured_llm.invoke(inp)

        chain = RunnableLambda(lambda x: _runner(x))
        return chain.batch(items)

    @property
    def model_name(self) -> str:
        return self._model
