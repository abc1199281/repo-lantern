"""LangSmith observability setup.

Configures LangSmith tracing for LangChain/LangGraph components.
LangSmith is the native observability platform for LangChain — once the
environment variables are set, all LangChain invocations (ChatModel.invoke,
chain.batch, LangGraph workflow execution) are automatically traced.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lantern_cli.config.models import LangSmithConfig

logger = logging.getLogger(__name__)


def configure_langsmith(config: LangSmithConfig) -> bool:
    """Configure LangSmith tracing via environment variables.

    LangChain automatically picks up the following env vars:
    - ``LANGCHAIN_TRACING_V2``: Enable tracing (``"true"``).
    - ``LANGCHAIN_API_KEY``: LangSmith API key.
    - ``LANGCHAIN_PROJECT``: Project name for grouping traces.
    - ``LANGCHAIN_ENDPOINT``: LangSmith API endpoint URL.

    Args:
        config: LangSmithConfig with tracing settings.

    Returns:
        ``True`` if tracing was successfully enabled, ``False`` otherwise.
    """
    if not config.enabled:
        logger.debug("LangSmith tracing is disabled")
        return False

    # Resolve API key from the configured environment variable
    api_key = os.environ.get(config.api_key_env, "")
    if not api_key:
        logger.warning(
            "LangSmith tracing is enabled but %s is not set. "
            "Tracing will be skipped. Set the environment variable to enable tracing.",
            config.api_key_env,
        )
        return False

    # Set the environment variables that LangChain reads
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = config.project
    os.environ["LANGCHAIN_ENDPOINT"] = config.endpoint

    logger.info(
        "LangSmith tracing enabled (project=%s, endpoint=%s)",
        config.project,
        config.endpoint,
    )
    return True
